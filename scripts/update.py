"""
Nucleus Update Utility

Modes:
  1. Auto-Update  - Deploy a new version from a USB drive (or any directory) to
                    a live installation. Uses native directory picker dialogs.
                    Only the standard library is needed for the copy and backup
                    steps; database migrations are run via the live installation's
                    own Python environment.

  2. Manual Update - Run database migrations and settings sync on the current
                     installation. Automatically re-executes under the project
                     virtualenv so dependencies do not need to be pre-activated.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# --- PATH SETUP ---
# Allows this script to be run from any working directory.
current_file = Path(__file__).resolve()
project_root = (
    current_file.parent.parent
    if current_file.parent.name == "scripts"
    else current_file.parent
)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
os.chdir(project_root)
# ------------------


# ---------------------------------------------------------------------------
# Virtualenv auto-detection
# ---------------------------------------------------------------------------

def _find_venv_python() -> Path | None:
    """
    Locates the Python interpreter inside the project virtualenv.
    Checks venv/ (standard), then .direnv/python-*/ (direnv-managed).
    Returns None when no virtualenv is found.
    """
    # Standard venv location
    if sys.platform == "win32":
        candidate = project_root / "venv" / "Scripts" / "python.exe"
    else:
        candidate = project_root / "venv" / "bin" / "python"

    if candidate.exists():
        return candidate

    # direnv-managed virtualenv (.direnv/python-3.x.x/bin/python)
    direnv_dir = project_root / ".direnv"
    if direnv_dir.exists():
        matches = sorted(direnv_dir.glob("python-*/bin/python"))
        if matches:
            return matches[0]

    return None


def _reexec_under_venv():
    """
    Re-executes this script under the project virtualenv Python so that
    core imports (sqlmodel, passlib, etc.) are always available.

    Passes --venv-reexec on the command line so the re-launched process
    knows not to re-enter this function, preventing an infinite loop.

    This function only runs when not already inside the project venv.
    It must be called before any import that requires installed packages.
    """
    # Already been re-exec'd — do not loop.
    if "--venv-reexec" in sys.argv:
        return

    venv_python = _find_venv_python()
    if venv_python is None:
        print("WARNING: No virtualenv found in this project directory.")
        print(
            "  Dependencies may be missing. Create one with:\n"
            "    python -m venv venv && pip install -r requirements.txt"
        )
        print("  Continuing with the current Python interpreter...\n")
        return

    current_python = Path(sys.executable).resolve()
    if current_python == venv_python.resolve():
        return  # Already running under the correct Python

    # Re-exec under the venv Python, forwarding all arguments plus the sentinel flag.
    print(f"Switching to virtualenv: {venv_python}")
    args = [str(venv_python)] + sys.argv + ["--venv-reexec"]
    os.execv(str(venv_python), args)
    # os.execv replaces this process — code below never runs.


# ---------------------------------------------------------------------------
# Auto-update configuration
# ---------------------------------------------------------------------------

# Items to skip when copying from source to live installation.
# The live database and backups folder are always preserved.
SKIP_FROM_COPY = {
    ".git",
    ".gitignore",
    ".gitattributes",
    ".direnv",
    "venv",
    ".envrc",
    "CLAUDE.md",
    ".claude",
    "scripts",
    "tests",
    "spikes",
    "screenshots",
    "backups",       # never overwrite live backups
    "hackspace.db",  # never overwrite live database
    "__pycache__",
}

# Items to delete from the live installation after copying.
# Handles the case where dev artifacts were included in a previous deployment.
DELETE_FROM_LIVE = {
    ".git",
    ".gitignore",
    ".gitattributes",
    ".direnv",
    "venv",
    ".envrc",
    "CLAUDE.md",
    ".claude",
    "scripts",
    "tests",
    "spikes",
    "screenshots",
}

# Files and directories that must always be present in the source.
REQUIRED_FILES = {
    "nucleus.py",
    "requirements.txt",
    "core",
    "screens",
    "theme",
    "LICENSE.md",
}


# ---------------------------------------------------------------------------
# Auto-update helpers
# ---------------------------------------------------------------------------

def _pick_directory(title: str) -> Path | None:
    """
    Opens a native directory picker dialog.
    Falls back to manual text input if tkinter is unavailable (e.g. headless).
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title=title)
        root.destroy()
        return Path(path) if path else None
    except Exception:
        raw = input(f"{title}\n  Enter path manually: ").strip()
        return Path(raw) if raw else None


def _check_write_access(target_dir: Path) -> bool:
    """
    Tests whether the current process can create files in target_dir.
    Uses a temporary probe file to catch permission errors before any real
    work is done, so the user gets a single clean error up front rather than
    mid-operation failures.
    """
    probe = target_dir / ".nucleus_write_probe"
    try:
        probe.touch()
        probe.unlink()
        return True
    except (PermissionError, OSError):
        return False


def _validate_source(source_dir: Path, live_dir: Path | None) -> bool:
    """
    Checks that the source directory contains all required app files.

    Two checks are performed:
      1. Required files — a baseline set of files/directories that must always
         be present regardless of whether a live installation exists.
      2. Live comparison — if a live installation is provided, any file or
         directory present in live (that is not a dev artifact or database) is
         checked against the source. Missing items are reported as warnings so
         nothing is silently left behind.

    Returns True if the source looks complete, False if critical files are
    missing (warnings about live-only files do not block the update).
    """
    missing_required = []
    for name in sorted(REQUIRED_FILES):
        if not (source_dir / name).exists():
            missing_required.append(name)

    if missing_required:
        print("  ERROR: The following required files are missing from the source:")
        for name in missing_required:
            print(f"    - {name}")
        return False

    print(f"  Required files: all {len(REQUIRED_FILES)} present.")

    if live_dir and live_dir.exists():
        missing_from_source = []
        for live_item in sorted(live_dir.rglob("*")):
            parts = live_item.relative_to(live_dir).parts
            if any(
                p in SKIP_FROM_COPY or p.startswith(".")
                for p in parts
            ):
                continue
            if live_item.name == "__pycache__" or live_item.suffix == ".pyc":
                continue
            if live_item.is_file():
                relative = live_item.relative_to(live_dir)
                if not (source_dir / relative).exists():
                    missing_from_source.append(str(relative))

        if missing_from_source:
            print(
                f"\n  WARNING: {len(missing_from_source)} file(s) found in the live"
                " installation are not present in the update source."
            )
            print("  These files will NOT be updated and may be out of date:")
            for name in missing_from_source:
                print(f"    - {name}")
            print()
            proceed = input("  Continue anyway? (y/N): ").strip().lower()
            if proceed != "y":
                return False
        else:
            print("  Live comparison: source contains all files from live installation.")

    return True


def _find_live_python(live_dir: Path) -> str:
    """
    Locates the Python interpreter in the live installation's virtualenv.
    Checks for a standard venv/ first, then a direnv-managed .direnv/python-*/,
    then falls back to the system Python.
    """
    import glob as _glob

    if sys.platform == "win32":
        candidates = [live_dir / "venv" / "Scripts" / "python.exe"]
    else:
        candidates = [
            live_dir / "venv" / "bin" / "python",
            *sorted(
                Path(p)
                for p in _glob.glob(
                    str(live_dir / ".direnv" / "python-*" / "bin" / "python")
                )
            ),
        ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _backup_live_database(live_dir: Path) -> bool:
    """Backs up the live database into the live installation's backups folder."""
    db_file = live_dir / "hackspace.db"
    if not db_file.exists():
        print("  WARNING: No database found in live directory. Skipping backup.")
        return True

    backup_dir = live_dir / "backups"
    backup_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%m%d%y_%H%M")
    backup_path = backup_dir / f"db_preupdate_backup_{date_str}.db"
    try:
        shutil.copy2(db_file, backup_path)
        print(f"  Backup created: {backup_path}")
        return True
    except Exception as exc:
        print(f"  ERROR: Backup failed: {exc}")
        return False


def _copy_update_files(source_dir: Path, live_dir: Path):
    """
    Copies all app files from source to live, skipping dev artifacts, dotfiles,
    and the live database. Existing files in the live directory are overwritten.
    Write access is assumed to have been verified before this function is called.
    """
    copied = 0
    skipped = 0
    errors = []

    for item in sorted(source_dir.iterdir()):
        if item.name in SKIP_FROM_COPY or item.name.startswith("."):
            skipped += 1
            continue
        dest = live_dir / item.name
        try:
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(
                    item,
                    dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            else:
                shutil.copy2(item, dest)
            copied += 1
        except Exception as exc:
            errors.append((item.name, str(exc)))

    print(f"  Copied {copied} items, skipped {skipped}.")
    if errors:
        print(f"  {len(errors)} item(s) failed to copy:")
        for name, msg in errors:
            print(f"    - {name}: {msg}")


def _remove_dev_artifacts(live_dir: Path):
    """
    Removes dev-only files and directories from the live installation, and
    sweeps the entire tree for any leftover __pycache__ directories.
    """
    removed = []
    errors = []

    for name in sorted(DELETE_FROM_LIVE):
        target = live_dir / name
        if not target.exists():
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(name)
        except Exception as exc:
            errors.append((name, str(exc)))

    for cache_dir in live_dir.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)

    if removed:
        print(f"  Removed: {', '.join(removed)}")
    else:
        print("  No dev artifacts found to remove.")

    if errors:
        print(f"  {len(errors)} item(s) could not be removed:")
        for name, msg in errors:
            print(f"    - {name}: {msg}")


def _run_live_migrations(live_dir: Path):
    """
    Runs database migrations in the live installation by invoking its own
    Python interpreter so the correct dependencies are used.
    """
    python = _find_live_python(live_dir)
    print(f"  Using Python: {python}")

    migration_code = (
        "import sys, os; "
        f"sys.path.insert(0, {str(live_dir)!r}); "
        f"os.chdir({str(live_dir)!r}); "
        "from core import services, square_service; "
        "from core.config import settings; "
        "from core.database import create_db_and_tables, run_migrations; "
        "create_db_and_tables(); "
        "run_migrations(); "
        "print('  Migrations applied.'); "
        "v = settings.APP_VERSION; "
        "services.set_setting('app_version', v); "
        "print(f'  Version updated to: {v}')"
    )
    result = subprocess.run(
        [python, "-c", migration_code],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"  WARNING: Migration step reported errors:\n{result.stderr.strip()}")
    else:
        print("  Migrations complete.")


def _print_elevation_hint(live_dir: Path):
    """
    Prints a platform-specific hint for re-running the script with elevated
    privileges when the live installation directory is not writable.
    """
    script_path = current_file

    print("\n  The live directory is not writable by the current user.")
    print(f"  Directory: {live_dir}\n")

    if sys.platform == "win32":
        print(
            "  On Windows, re-run this script from an Administrator command prompt:\n"
            f"    python {script_path}"
        )
    elif sys.platform == "darwin":
        print(
            "  On macOS, re-run this script with sudo:\n"
            f"    sudo python3 {script_path}"
        )
    else:
        print(
            "  On Linux, re-run this script with sudo:\n"
            f"    sudo python3 {script_path}"
        )


# ---------------------------------------------------------------------------
# Auto-update entry point
# ---------------------------------------------------------------------------

def run_auto_update():
    """
    Guided deployment workflow:
      1. Pick the live installation directory via a file picker dialog.
      2. Pick the update source directory (USB drive or folder).
      3. Check write access to the live directory — abort with instructions if denied.
      4. Back up the live database.
      5. Copy updated app files from source to live.
      6. Remove dev-only artifacts from the live installation.
      7. Run database migrations using the live installation's Python.
    """
    print("=== Nucleus Auto-Update ===\n")
    print("Two directory picker dialogs will open.")
    print("First: select the live installation. Second: select the update source.\n")

    live_dir = _pick_directory("Step 1 of 2 - Select Live Installation Directory")
    if not live_dir or not live_dir.exists():
        print("ERROR: Invalid or missing live directory. Aborting.")
        return

    source_dir = _pick_directory("Step 2 of 2 - Select Update Source Directory (USB Drive)")
    if not source_dir or not source_dir.exists():
        print("ERROR: Invalid or missing source directory. Aborting.")
        return

    print(f"  Live installation : {live_dir}")
    print(f"  Update source     : {source_dir}")

    confirm = input(
        "\nThis will overwrite files in the live installation. Proceed? (y/N): "
    ).strip().lower()
    if confirm != "y":
        print("Update cancelled.")
        return

    print("\n--- Step 1: Validating Source ---")
    if not _validate_source(source_dir, live_dir):
        print("Update aborted.")
        return

    print("\n--- Step 2: Checking Write Access ---")
    if not _check_write_access(live_dir):
        _print_elevation_hint(live_dir)
        print("\nUpdate aborted.")
        return
    print("  Write access confirmed.")

    print("\n--- Step 3: Backing Up Database ---")
    if not _backup_live_database(live_dir):
        abort = input("  Backup failed. Continue anyway? (y/N): ").strip().lower()
        if abort != "y":
            print("Update aborted.")
            return

    print("\n--- Step 4: Copying Update Files ---")
    _copy_update_files(source_dir, live_dir)

    print("\n--- Step 5: Removing Dev Artifacts ---")
    _remove_dev_artifacts(live_dir)

    print("\n--- Step 6: Running Database Migrations ---")
    _run_live_migrations(live_dir)

    print("\nAuto-update complete.")


# ---------------------------------------------------------------------------
# Manual update (migrations only on current installation)
# ---------------------------------------------------------------------------

def _load_core():
    """
    Lazily imports core modules after the venv re-exec has happened.
    Called only for the manual update path so the auto-update copy step
    has no dependency on installed packages.
    """
    global services, settings, create_db_and_tables, run_migrations, SETTINGS_FILE
    try:
        from core import services as _services
        from core.config import settings as _settings, SETTINGS_FILE as _sf
        from core.database import (
            create_db_and_tables as _cdbt,
            run_migrations as _rm,
        )
    except ImportError as exc:
        print(f"\nERROR: Could not import core modules: {exc}")
        print(
            "  Make sure the project virtualenv is active or run this script\n"
            "  from the project root so dependencies can be found.\n"
            "  Create the venv with:\n"
            "    python -m venv venv && pip install -r requirements.txt"
        )
        sys.exit(1)

    services = _services
    settings = _settings
    SETTINGS_FILE = _sf
    create_db_and_tables = _cdbt
    run_migrations = _rm


def backup_database():
    """Backs up the database before any changes are applied."""
    db_file = project_root / "hackspace.db"
    backup_dir = project_root / "backups"

    if not db_file.exists():
        print("WARNING: No database found. Nothing to backup.")
        return

    backup_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%m%d%y_%H%M")
    backup_filename = f"db_premigrate_backup_{date_str}.db"
    backup_path = backup_dir / backup_filename

    try:
        shutil.copy2(db_file, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as exc:
        print(f"Backup Failed: {exc}")


def seed_settings_from_file():
    """
    Seeds the AppSetting table with values read from theme/settings.txt.
    Only populates keys that do not already exist in the database so that
    values an admin has changed via the Settings tab are never overwritten.
    Falls back to built-in defaults for any key not present in the file.

    New setting keys added in each release are seeded automatically because
    initialize_default_settings() holds the full canonical defaults list.
    """
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

    services.initialize_default_settings(seed)
    print(
        "  Space operations settings  : membership_grace_period_days, day_pass_cost_credits,"
    )
    print(
        "                               max_concurrent_signins, backup_retention_days"
    )
    print(
        "  Reporting/branding settings: app_currency_name, default_export_format,"
        " report_header_text, staff_email"
    )
    print(
        "  Security settings          : min_password_length, sql_console_enabled,"
        " login_attempt_limit"
    )
    print("  Done. Existing values were not overwritten.")


def prompt_version_update():
    """
    Shows both the version from settings.txt (code version) and the version
    stored in the database, then optionally updates the stored version.
    If confirmed, writes the new version to the AppSetting table, overwriting
    whatever value was previously stored. Skips silently on empty input.
    """
    db_version = services.get_setting("app_version", "(not set)")
    code_version = settings.APP_VERSION

    print(f"\n  Version in settings.txt : {code_version}")
    print(f"  Version stored in DB    : {db_version}")

    if db_version == code_version:
        print("  Versions match. No update needed.")

    answer = input("\nUpdate DB version number? (y/N): ").strip().lower()
    if answer != "y":
        return

    new_version = input(f"  Enter new version number [{code_version}]: ").strip()

    if not new_version:
        new_version = code_version

    if not new_version:
        print("  No version available. Skipping.")
        return

    services.set_setting("app_version", new_version)
    print(f"  Version updated to: {new_version}")


def run_update():
    """Runs migrations and settings sync on the current installation."""
    # Re-exec under the project venv before importing anything from core.
    # This makes the script work when called directly without activating the venv.
    _reexec_under_venv()

    _load_core()

    print(f"Target Database: {project_root / 'hackspace.db'}")

    backup_database()

    print("\n--- Verifying Tables ---")
    create_db_and_tables()
    print("Core Tables Verified.")

    print("\n--- Verifying Columns ---")
    run_migrations()

    print("\n--- Verifying Settings ---")
    seed_settings_from_file()
    print("Settings Verified.")

    print("\n--- Version ---")
    prompt_version_update()

    print("\nUpdate Complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Strip the internal sentinel flag from argv so it is not shown to the user
    # or forwarded to any subprocess.
    if "--venv-reexec" in sys.argv:
        sys.argv.remove("--venv-reexec")

    print("Nucleus Update Utility")
    print("  1. Auto-Update  (deploy from USB to live installation)")
    print("  2. Manual Update (run migrations on this installation)")
    choice = input("\nChoose [1/2]: ").strip()
    if choice == "1":
        run_auto_update()
    else:
        run_update()
