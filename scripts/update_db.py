import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- ROBUST PATH SETUP ---
current_file = Path(__file__).resolve()
if current_file.parent.name in ("scripts", "core"):
    project_root = current_file.parent.parent
else:
    project_root = current_file.parent

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

os.chdir(project_root)

# -------------------------


# Import models to ensure they are registered with SQLModel
from core import services  # noqa: E402
from core.config import settings  # noqa: E402
from core.database import create_db_and_tables, run_migrations  # noqa: E402


def backup_database():
    """Backs up the database before any changes are applied."""
    db_file = "hackspace.db"
    backup_dir = "backups"

    if not os.path.exists(db_file):
        print("⚠️  No database found. Nothing to backup.")
        return

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # Format: db_premigrate_backup_MMDDYY_HHMM.db
    date_str = datetime.now().strftime("%m%d%y_%H%M")
    backup_filename = f"db_premigrate_backup_{date_str}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        shutil.copy2(db_file, backup_path)
        print(f"✅ Backup created: {backup_path}")
    except Exception as e:
        print(f"❌ Backup Failed: {e}")


def seed_settings_from_file():
    """
    Seeds the AppSetting table with values read from theme/settings.txt.
    Only populates keys that do not already exist in the database so that
    values an admin has changed via the Settings tab are never overwritten.
    Falls back to built-in defaults for any key not present in the file.

    New setting keys added in each release are seeded automatically because
    initialize_default_settings() holds the full canonical defaults list.
    """
    from core.config import SETTINGS_FILE

    if os.path.exists(SETTINGS_FILE):
        print(f"  Reading from: {SETTINGS_FILE}")
        seed = {
            "hackspace_name": settings.HACKSPACE_NAME,
            "tag_name": settings.TAG_NAME,
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "ascii_logo": settings.ASCII_LOGO,
            "logout_timeout_minutes": "10",
        }
        print(f"  hackspace_name : {settings.HACKSPACE_NAME}")
        print(f"  tag_name       : {settings.TAG_NAME}")
        print(f"  app_name       : {settings.APP_NAME}")
        print(f"  app_version    : {settings.APP_VERSION}")
        print(f"  ascii_logo     : {'(set)' if settings.ASCII_LOGO else '(empty)'}")
    else:
        print(f"  WARNING: {SETTINGS_FILE} not found. Using built-in defaults.")
        seed = {
            "logout_timeout_minutes": "10",
        }

    # initialize_default_settings seeds all keys not yet in the DB, including
    # new keys added in this release (space ops, security, reporting settings).
    # Existing admin-configured values are never overwritten.
    services.initialize_default_settings(seed)
    print(
        "  Space operations settings  : membership_grace_period_days, day_pass_cost_credits,"
    )
    print(
        "                               max_concurrent_signins, backup_retention_days"
    )
    print(
        "  Reporting/branding settings: app_currency_name, default_export_format, report_header_text, staff_email"
    )
    print(
        "  Security settings          : min_password_length, sql_console_enabled, login_attempt_limit"
    )
    print("  Done. Existing values were not overwritten.")


def prompt_version_update():
    """
    Asks whether to update the stored app version number.
    If confirmed, writes the new version to the AppSetting table, overwriting
    whatever value was previously stored. Skips silently on empty input.
    """
    answer = input("\nUpdate app version number? (y/N): ").strip().lower()
    if answer != "y":
        return

    current = services.get_setting("app_version", "(not set)")
    print(f"  Current version: {current}")
    new_version = input("  Enter new version number: ").strip()

    if not new_version:
        print("  No version entered. Skipping.")
        return

    services.set_setting("app_version", new_version)
    print(f"  Version updated to: {new_version}")


def update_database():
    print(f"Target Database: {project_root / 'hackspace.db'}")

    # 1. Backup
    backup_database()

    # 2. Ensure tables exist
    print("\n--- Verifying Tables ---")
    create_db_and_tables()
    print("Core Tables Verified.")

    # 3. Apply all column migrations (single source of truth in core/database.py)
    print("\n--- Verifying Columns ---")
    run_migrations()

    # 4. Seed any missing settings rows from settings.txt
    print("\n--- Verifying Settings ---")
    seed_settings_from_file()
    print("Settings Verified.")

    # 5. Optionally update the app version number
    prompt_version_update()

    print("\nDatabase Update Complete.")


if __name__ == "__main__":
    update_database()
