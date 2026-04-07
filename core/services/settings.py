"""Application-level settings stored in the AppSetting table."""

from sqlmodel import Session

from core.database import engine
from core.models import AppSetting

__all__ = [
    "get_setting",
    "set_setting",
    "set_sensitive_setting",
    "sensitive_setting_is_configured",
    "get_sensitive_setting_value",
    "initialize_default_settings",
]


def get_setting(key: str, default: str = "") -> str:
    """Returns the value for a settings key, or default if not found."""
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return s.value if s else default


def set_setting(key: str, value: str):
    """Creates or updates a settings key."""
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        if s:
            s.value = value
        else:
            s = AppSetting(key=key, value=value)
        session.add(s)
        session.commit()


def set_sensitive_setting(key: str, value: str) -> None:
    """
    Stores a setting value and flags it as sensitive so the UI knows never to
    display it after saving. The value is stored in plaintext — the sensitivity
    flag is purely a UI-layer contract, not an encryption guarantee.
    Appropriate for API keys on a local SQLite deployment.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        if s:
            s.value = value
            s.is_sensitive = True
        else:
            s = AppSetting(key=key, value=value, is_sensitive=True)
        session.add(s)
        session.commit()


def sensitive_setting_is_configured(key: str) -> bool:
    """
    Returns True when a non-empty value has already been stored for a sensitive
    key. The UI uses this to decide whether to show an input field or the
    "configured / hidden" placeholder — it never needs the raw value.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return bool(s and s.value)


def get_sensitive_setting_value(key: str) -> str:
    """
    Returns the raw value stored for a sensitive setting key.
    This function is intended for internal service and email use only.
    It must never be called from a screen or any UI layer.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return s.value if s else ""


def initialize_default_settings(seed_values: dict = None):
    """
    Seeds the AppSetting table with default values on first run.
    Existing keys are never overwritten.
    seed_values allows the caller to pass file-based values as initial defaults.
    """
    defaults = {
        "hackspace_name": "Hackspace",
        "tag_name": "Makerspace",
        "app_name": "Nucleus Daemon",
        "app_version": "v0.9.79",
        "ascii_logo": "",
        "logout_timeout_minutes": "10",
        # Space operations
        "membership_grace_period_days": "0",
        "day_pass_cost_credits": "0",
        "max_concurrent_signins": "0",
        "backup_retention_days": "30",
        "backup_enabled": "false",
        # 24-hour HH:MM time at which the scheduled backup runs
        "backup_time": "02:00",
        # Optional email address to receive a copy of the backup file
        "backup_email": "",
        # Reporting and branding
        "app_currency_name": "Credits",
        "default_export_format": "csv",
        "report_header_text": "",
        "staff_email": "",
        # Security
        "min_password_length": "8",
        "sql_console_enabled": "true",
        "login_attempt_limit": "0",
        # Email reporting — resend_api_key is seeded separately via set_sensitive_setting
        "report_from_email": "onboarding@resend.dev",
        "report_to_email": "",
        "email_reports_enabled": "false",
        # 24-hour HH:MM time at which the daily report email is dispatched
        "report_send_time": "07:00",
        # Error email notifications — sends an email whenever a severity=error
        # notification is triggered in the application
        "error_email_enabled": "false",
        "error_email_to": "",
        # Monthly transaction report — fires on the 1st of each month for the previous month
        "monthly_transaction_report_enabled": "false",
        # Stores the last reported period as "YYYY-MM" to prevent duplicate sends
        "monthly_report_last_sent_month": "",
    }
    if seed_values:
        defaults.update(seed_values)

    with Session(engine) as session:
        for key, value in defaults.items():
            if not session.get(AppSetting, key):
                session.add(AppSetting(key=key, value=value))
        session.commit()
