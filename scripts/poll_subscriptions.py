#!/usr/bin/env python3
"""
Poll Square subscription status for all enrolled members.

Intended to be run once daily (e.g. via cron or a system scheduler) to keep
the local subscription status in sync with Square. For each member that has a
square_subscription_id on file, the script fetches the current status from the
Square API and updates the User record.

No access control changes are made automatically — status is updated for staff
review. Staff can act on lapsed subscriptions through the Purchases tab in
the Nucleus TUI.

Usage:
    python scripts/poll_subscriptions.py

Exit codes:
    0 — all polls succeeded (or no subscriptions on file)
    1 — one or more polls returned an error
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so core imports resolve correctly
# when the script is run from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import create_db_and_tables, run_migrations
from core import square_service


def main():
    # Initialise the database and apply any pending schema migrations before
    # calling service functions that query the User table.
    create_db_and_tables()
    run_migrations()

    polled, errors = square_service.poll_all_active_subscriptions()

    print(f"Subscription poll complete: {polled} updated, {errors} errors.")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
