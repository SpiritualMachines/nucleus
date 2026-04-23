import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from textual.app import App

from core import models, services
from core.config import settings
from core.database import create_db_and_tables, run_migrations
from screens.login import LoginScreen


class HackspaceApp(App):
    # Fallback theme used before the DB is available; overridden in on_mount
    CSS_THEME = "nord"

    # This tells Textual to load CSS from the external file
    CSS_PATH = "theme/app.tcss"

    # Set the App Title from Config
    TITLE = settings.HACKSPACE_NAME

    # FIX: Use Optional[] instead of | for Python < 3.10 compatibility
    current_user: Optional[models.User] = None

    def notify(
        self,
        message: str,
        *,
        title: str = "",
        severity: str = "information",
        timeout: float = None,
    ) -> None:
        """
        Extends the Textual notify method to optionally send an email to staff
        whenever a severity='error' notification is triggered. The email is
        dispatched in a background daemon thread so it never blocks the UI.
        The feature is gated by the error_email_enabled setting and requires
        the Resend API key and error_email_to address to be configured.
        """
        if timeout is not None:
            super().notify(message, title=title, severity=severity, timeout=timeout)
        else:
            super().notify(message, title=title, severity=severity)

        if severity == "error":
            import traceback as _tb

            tb = _tb.format_exc()
            threading.Thread(
                target=self._send_error_notification_email,
                args=(message, tb),
                daemon=True,
            ).start()

    def _send_error_notification_email(
        self, error_message: str, traceback_info: str = ""
    ) -> None:
        """
        Background thread target that emails an error notification if the
        feature is enabled and all required settings are configured.
        Never calls self.notify() to avoid recursion — logs to stdout only.
        """
        try:
            from core.email_service import send_error_notification_email

            send_error_notification_email(
                error_message=error_message,
                traceback_info=traceback_info,
            )
        except Exception as e:
            print(f"[Error Email] Failed to send error notification email: {e}")

    def on_mount(self):
        # 1. Apply the persisted theme (falls back to nord if not yet set)
        create_db_and_tables()
        run_migrations()
        saved_theme = services.get_setting("app_theme", "nord")
        self.theme = saved_theme

        # 2. Start background scheduler threads.
        #    Maintenance (membership expiry) runs immediately and then daily at midnight.
        #    Backup runs on its own thread at the admin-configured time (never on startup).
        #    Email reports run on their own thread, firing at the admin-configured time.
        threading.Thread(target=self.run_maintenance_scheduler, daemon=True).start()
        threading.Thread(target=self.run_backup_scheduler, daemon=True).start()
        threading.Thread(target=self.run_email_scheduler, daemon=True).start()
        threading.Thread(target=self.run_monthly_report_scheduler, daemon=True).start()

        # 3. Seed settings from the file on first run; existing keys are never overwritten
        services.initialize_default_settings(
            {
                "hackspace_name": settings.HACKSPACE_NAME,
                "tag_name": settings.TAG_NAME,
                "app_name": settings.APP_NAME,
                "app_version": settings.APP_VERSION,
                "ascii_logo": settings.ASCII_LOGO,
                "logout_timeout_minutes": "10",
            }
        )

        # Ensure the resend_api_key row exists as a sensitive entry so that
        # sensitive_setting_is_configured() can read it on the first launch even
        # before the admin has entered a value.  Only seeds when no row exists yet.
        if not services.sensitive_setting_is_configured("resend_api_key"):
            from core.models import AppSetting
            from core.database import engine
            from sqlmodel import Session

            with Session(engine) as _s:
                if not _s.get(AppSetting, "resend_api_key"):
                    _s.add(
                        AppSetting(key="resend_api_key", value="", is_sensitive=True)
                    )
                    _s.commit()

        # DB settings take precedence over the file for the app title
        self.title = services.get_setting("hackspace_name", settings.HACKSPACE_NAME)

        self.push_screen(LoginScreen())

    def run_maintenance_scheduler(self):
        """
        Long-running daemon thread for membership expiry checks.
        Runs immediately on launch, then sleeps until 00:01 each night and repeats.
        Backup is handled separately by run_backup_scheduler so it can be
        scheduled at an admin-configured time rather than always running at startup.
        """
        # Run immediately at launch so expiry checks are never skipped on a fresh start
        self.run_daily_maintenance()

        while True:
            # Calculate seconds until one minute past midnight
            now = datetime.now()
            next_run = (now + timedelta(days=1)).replace(
                hour=0, minute=1, second=0, microsecond=0
            )
            sleep_seconds = (next_run - now).total_seconds()
            time.sleep(sleep_seconds)
            self.run_daily_maintenance()

    def run_email_scheduler(self):
        """
        Daemon thread that fires the daily email report at the admin-configured time
        (report_send_time setting, HH:MM 24-hour format, default 07:00).

        Polls every 60 seconds rather than sleeping for hours. This makes the
        scheduler resilient to system sleep and hibernate — a single long sleep
        would expire the moment the system resumed, causing the email to fire at
        whatever time the machine woke up rather than the configured time.

        The last-sent date is persisted in the database so that restarting the app
        does not cause a duplicate send on the same calendar day.
        """
        while True:
            time.sleep(60)
            now = datetime.now()
            today = now.date()

            # Re-read the last-sent date from the DB on every poll so that a
            # restart (or a manual send from the Settings screen) is always
            # recognised. Reading inside the loop also avoids a race condition
            # with create_db_and_tables() on the very first launch.
            sent_date = None
            try:
                last_sent_str = services.get_setting("report_last_sent_date", "")
                if last_sent_str:
                    sent_date = datetime.strptime(last_sent_str, "%Y-%m-%d").date()
            except Exception:
                sent_date = None

            # Re-read the setting on every poll so changes take effect immediately
            send_time_str = services.get_setting("report_send_time", "07:00")
            try:
                parts = send_time_str.strip().split(":")
                send_hour = int(parts[0])
                send_minute = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                send_hour, send_minute = 7, 0
                print(
                    f"[Email Scheduler] Invalid report_send_time '{send_time_str}', using 07:00"
                )

            target = now.replace(
                hour=send_hour, minute=send_minute, second=0, microsecond=0
            )

            # Fire if we have reached or passed the target time today and have
            # not already sent for today. This window stays open for the rest of
            # the day so a report is not skipped if the machine was asleep at
            # exactly the configured minute.
            if now >= target and sent_date != today:
                print(
                    f"[Email Scheduler] Triggering daily email report at {now} "
                    f"(configured time {send_hour:02d}:{send_minute:02d})"
                )
                self.send_daily_email_report()
                sent_date = today
                services.set_setting("report_last_sent_date", str(today))

    def run_monthly_report_scheduler(self):
        """
        Daemon thread that fires the monthly transaction report on the 1st of each
        month. The report covers all transactions from the previous calendar month
        and is sent to the same recipient list as the daily report.

        Polls every 60 seconds using the same pattern as run_email_scheduler so the
        scheduler survives system sleep. The last-sent period is persisted as "YYYY-MM"
        in monthly_report_last_sent_month to prevent duplicate sends after a restart.
        """
        while True:
            time.sleep(60)

            # Re-read the feature flag on every poll so setting changes take effect immediately
            enabled = (
                services.get_setting(
                    "monthly_transaction_report_enabled", "false"
                ).lower()
                == "true"
            )
            if not enabled:
                continue

            now = datetime.now()

            # Only fire on the 1st day of the month
            if now.day != 1:
                continue

            # Determine which month the report covers (the month just ended)
            if now.month == 1:
                report_year, report_month = now.year - 1, 12
            else:
                report_year, report_month = now.year, now.month - 1

            report_month_key = f"{report_year}-{report_month:02d}"

            # Re-read the last-sent marker from the DB on every poll so restarts
            # and manual resets are recognised without needing an app restart.
            last_sent = ""
            try:
                last_sent = services.get_setting("monthly_report_last_sent_month", "")
            except Exception:
                last_sent = ""

            if last_sent == report_month_key:
                continue

            print(
                f"[Monthly Report Scheduler] Triggering monthly transaction report"
                f" for {report_month_key} at {now}"
            )
            self.send_monthly_transaction_report_email(report_year, report_month)
            services.set_setting("monthly_report_last_sent_month", report_month_key)

    def run_backup_scheduler(self):
        """
        Daemon thread that fires the database backup at the admin-configured time
        (backup_time setting, HH:MM 24-hour format, default 02:00).

        Uses the same 60-second poll pattern as the email scheduler so the scheduler
        remains resilient to system sleep. The backup only runs when backup_enabled
        is set to "true". A backed_up_date tracker ensures exactly one backup per
        calendar day regardless of how many times the clock crosses the target minute.
        """
        backed_up_date = None

        while True:
            time.sleep(60)

            # Re-read settings on every poll so changes take effect without restart
            enabled = services.get_setting("backup_enabled", "false").lower() == "true"
            if not enabled:
                continue

            now = datetime.now()
            today = now.date()

            backup_time_str = services.get_setting("backup_time", "02:00")
            try:
                parts = backup_time_str.strip().split(":")
                backup_hour = int(parts[0])
                backup_minute = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                backup_hour, backup_minute = 2, 0
                print(
                    f"[Backup Scheduler] Invalid backup_time '{backup_time_str}', using 02:00"
                )

            target = now.replace(
                hour=backup_hour, minute=backup_minute, second=0, microsecond=0
            )

            if now >= target and backed_up_date != today:
                print(
                    f"[Backup Scheduler] Triggering backup at {now} "
                    f"(configured time {backup_hour:02d}:{backup_minute:02d})"
                )
                self.perform_daily_backup()
                backed_up_date = today

    def run_daily_maintenance(self):
        """
        Runs membership-expiry tasks. Called at launch and once per day just after
        midnight. Backup is intentionally excluded here — it runs at an admin-configured
        time via run_backup_scheduler.
        """
        self.check_expired_memberships()

    def check_expired_memberships(self):
        """
        Wrapper that calls the core service and surfaces any unexpected errors to the
        UI notification system so they are visible to staff rather than silently lost.
        """
        try:
            services.check_expired_memberships()
        except Exception as e:
            self.call_from_thread(
                self.notify,
                f"Membership check error: {str(e)}",
                severity="error",
            )

    def send_daily_email_report(self):
        """
        Sends the daily membership summary email if reports are enabled and all
        required settings (API key, to-address) have been configured. Errors and
        the "not configured" case are surfaced as notifications so staff can act
        on them without checking logs.
        """
        try:
            from core.email_service import send_daily_report
            from core import services

            # Check prerequisites first to provide better diagnostic feedback
            enabled = (
                services.get_setting("email_reports_enabled", "false").lower() == "true"
            )
            if not enabled:
                # Silently skip if disabled (expected behavior)
                return

            api_key = services.get_sensitive_setting_value("resend_api_key")
            to_email = services.get_setting("report_to_email", "").strip()

            if not api_key:
                self.call_from_thread(
                    self.notify,
                    "Daily report skipped: Resend API key not configured.",
                    severity="warning",
                )
                return

            if not to_email:
                self.call_from_thread(
                    self.notify,
                    "Daily report skipped: Report recipient email not configured.",
                    severity="warning",
                )
                return

            # Prerequisites met, send the report
            sent = send_daily_report()
            if sent:
                self.call_from_thread(
                    self.notify, "Daily report email sent successfully."
                )
            else:
                # Fallback: shouldn't reach here if prerequisites are checked above,
                # but notify if it somehow returns False
                self.call_from_thread(
                    self.notify,
                    "Daily report failed to send (check logs).",
                    severity="error",
                )
        except Exception as e:
            self.call_from_thread(
                self.notify,
                f"Daily report email error: {str(e)}",
                severity="error",
            )

    def send_monthly_transaction_report_email(self, year: int, month: int) -> None:
        """
        Sends the monthly transaction report email if the feature is enabled and
        all required settings are configured. Errors are surfaced as UI notifications
        so staff are informed without having to check logs.
        """
        try:
            from core.email_service import send_monthly_transaction_report
            from core import services

            enabled = (
                services.get_setting(
                    "monthly_transaction_report_enabled", "false"
                ).lower()
                == "true"
            )
            if not enabled:
                return

            api_key = services.get_sensitive_setting_value("resend_api_key")
            to_email = services.get_setting("report_to_email", "").strip()

            if not api_key:
                self.call_from_thread(
                    self.notify,
                    "Monthly report skipped: Resend API key not configured.",
                    severity="warning",
                )
                return

            if not to_email:
                self.call_from_thread(
                    self.notify,
                    "Monthly report skipped: Report recipient email not configured.",
                    severity="warning",
                )
                return

            sent = send_monthly_transaction_report(year, month)
            if sent:
                self.call_from_thread(
                    self.notify, "Monthly transaction report email sent successfully."
                )
            else:
                self.call_from_thread(
                    self.notify,
                    "Monthly report failed to send (check logs).",
                    severity="error",
                )
        except Exception as e:
            self.call_from_thread(
                self.notify,
                f"Monthly report email error: {str(e)}",
                severity="error",
            )

    def perform_daily_backup(self):
        """
        Creates a copy of hackspace.db in /backups/ named db_backup_MMDDYY.db.
        Only runs when backup_enabled is "true". Skips silently if a backup for today
        already exists. After creating the backup, purges files beyond the
        backup_retention_days setting (0 = keep all). If backup_email is configured
        the backup file is also emailed as an attachment via Resend.
        """
        # Honour the enabled toggle — the scheduler checks this too, but defend here
        # in case perform_daily_backup is ever called directly.
        enabled = services.get_setting("backup_enabled", "false").lower() == "true"
        if not enabled:
            return

        db_file = "hackspace.db"
        backup_dir = "backups"

        # Skip if the database doesn't exist yet (first run ever)
        if not os.path.exists(db_file):
            return

        # Ensure backups directory exists
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir)
            except OSError as e:
                self.call_from_thread(
                    self.notify,
                    f"Backup Error: Could not create directory {e}",
                    severity="error",
                )
                return

        # Construct filename for today (MMDDYY)
        date_str = datetime.now().strftime("%m%d%y")
        backup_filename = f"db_backup_{date_str}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Copy only if today's backup does not already exist
        backup_created = False
        if not os.path.exists(backup_path):
            try:
                shutil.copy2(db_file, backup_path)
                backup_created = True
                self.call_from_thread(
                    self.notify, f"Daily Backup Created: {backup_filename}"
                )
            except Exception as e:
                self.call_from_thread(
                    self.notify, f"Backup Failed: {str(e)}", severity="error"
                )

        # Purge old backups beyond the retention window
        try:
            retention_days = int(services.get_setting("backup_retention_days", "30"))
        except Exception:
            retention_days = 30

        if retention_days > 0:
            try:
                backup_files = sorted(
                    [
                        f
                        for f in os.listdir(backup_dir)
                        if f.startswith("db_backup_") and f.endswith(".db")
                    ],
                    key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                )
                excess = len(backup_files) - retention_days
                if excess > 0:
                    for old_file in backup_files[:excess]:
                        os.remove(os.path.join(backup_dir, old_file))
            except Exception:
                pass  # Purge errors are non-fatal; the backup itself was already created

        # Email the backup file if an address has been configured
        if backup_created:
            backup_email = services.get_setting("backup_email", "").strip()
            if backup_email:
                try:
                    from core.email_service import send_backup_email

                    send_backup_email(backup_path, backup_filename, backup_email)
                    self.call_from_thread(
                        self.notify, f"Backup emailed to {backup_email}"
                    )
                except Exception as e:
                    self.call_from_thread(
                        self.notify,
                        f"Backup email failed: {str(e)}",
                        severity="error",
                    )


if __name__ == "__main__":
    app = HackspaceApp()
    app.run()
