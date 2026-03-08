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
    # Standard Library Textual Theme
    CSS_THEME = "nord"

    # This tells Textual to load CSS from the external file
    CSS_PATH = "theme/app.tcss"

    # Set the App Title from Config
    TITLE = settings.HACKSPACE_NAME

    # FIX: Use Optional[] instead of | for Python < 3.10 compatibility
    current_user: Optional[models.User] = None

    def on_mount(self):
        # 1. FORCE THE THEME PROGRAMMATICALLY
        self.theme = "nord"

        # 2. Start the daily maintenance scheduler in a single background thread.
        #    It runs all maintenance tasks immediately on launch, then repeats them
        #    every day just after midnight for as long as the app stays running.
        threading.Thread(target=self.run_maintenance_scheduler, daemon=True).start()

        # 3. Initialize DB, apply pending schema migrations, seed settings, then load UI
        create_db_and_tables()
        run_migrations()

        # Seed settings from the file on first run; existing keys are never overwritten
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

        # DB settings take precedence over the file for the app title
        self.title = services.get_setting("hackspace_name", settings.HACKSPACE_NAME)

        self.push_screen(LoginScreen())

    def run_maintenance_scheduler(self):
        """
        Long-running daemon thread that executes all daily maintenance tasks.
        Runs immediately on launch, then sleeps until 00:01 each night and repeats.
        Adding a new daily task only requires calling it inside run_daily_maintenance().
        """
        # Run immediately at launch so maintenance is never skipped on a fresh start
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

    def run_daily_maintenance(self):
        """
        Runs all daily maintenance tasks in sequence. Called at launch and once per
        day just after midnight. Each task is independent — a failure in one does not
        prevent the others from running.
        """
        self.perform_daily_backup()
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

    def perform_daily_backup(self):
        """
        Creates a copy of hackspace.db in /backups/ named db_backup_MMDDYY.db.
        Skips silently if a backup for today already exists. After creating the backup,
        purges files beyond the backup_retention_days setting (0 = keep all).
        get_setting calls fall back gracefully if the appsetting table is not yet
        available on first launch before DB initialisation completes.
        """
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
        if not os.path.exists(backup_path):
            try:
                shutil.copy2(db_file, backup_path)
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


if __name__ == "__main__":
    app = HackspaceApp()
    app.run()
