"""
import_community_contacts.py

One-time import script to merge community contact records from a CSV file into
the live database. Designed for the community_night_data.csv export format but
accepts any CSV following the same column layout.

Run from any directory:
    python scripts/import_community_contacts.py
    python scripts/import_community_contacts.py path/to/custom.csv

Duplicate detection: a row is skipped if a record with the same first name,
last name, and visit date (day precision) already exists. This makes the script
safe to re-run without creating duplicate entries.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup - resolve project root regardless of where this script is run from
# ---------------------------------------------------------------------------
current_file = Path(__file__).resolve()

if current_file.parent.name in ("scripts", "core"):
    project_root = current_file.parent.parent
else:
    project_root = current_file.parent

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

os.chdir(project_root)

db_path = project_root / "hackspace.db"
if not db_path.exists():
    print(f"Error: Database file not found at: {db_path}")
    print("Please run the main application first to initialize the database.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Imports that depend on project root being in sys.path
# ---------------------------------------------------------------------------
from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from core.models import CommunityContact  # noqa: E402

# ---------------------------------------------------------------------------
# CSV column names as they appear in the export file
# ---------------------------------------------------------------------------
COL_DATE = "Date"
COL_FIRST_NAME = "First Name"
COL_LAST_NAME = "Last Name"
COL_PRONOUNS = "Pronouns"
COL_AGE_RANGE = "Age Range"
COL_POSTAL = "Postal/Zip Code"
COL_HOW_HEARD = "How did you hear about us?"
COL_REASON = "What brought you here today?"
COL_CONNECT = "Let's stay connected!"
COL_EMAIL = "If you want to stay connected, leave us your email."

# Substrings used to identify each opt-in option within the multi-line
# "Let's stay connected!" cell value.
OPT_IN_UPDATES_MARKER = "updates about workshops"
OPT_IN_VOLUNTEER_MARKER = "interested in volunteering"
OPT_IN_TEACHING_MARKER = "interested in teaching"

# Date formats used in the CSV export (e.g. "Sep 29, 2025")
DATE_FORMATS = ["%b %d, %Y", "%B %d, %Y"]


def parse_date(raw: str) -> datetime:
    """Parse a human-readable date string from the CSV into a datetime object."""
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: '{raw}'")


def parse_opt_ins(cell: str) -> tuple[bool, bool, bool]:
    """
    Extract the three opt-in flags from the multi-line 'Let's stay connected!'
    cell. The cell may contain one or more of the following lines in any order:
        - 'Yes, I'd like to receive updates about workshops, events, and opportunities.'
        - 'I might be interested in volunteering.'
        - 'I might be interested in teaching/mentoring.'
    Returns (opt_in_updates, opt_in_volunteer, opt_in_teaching).
    """
    lower = cell.lower()
    return (
        OPT_IN_UPDATES_MARKER in lower,
        OPT_IN_VOLUNTEER_MARKER in lower,
        OPT_IN_TEACHING_MARKER in lower,
    )


def normalise_str(value: str | None) -> str | None:
    """Return None for empty/whitespace-only strings, otherwise strip."""
    if not value or not value.strip():
        return None
    return value.strip()


def find_existing(session: Session, first_name: str, last_name: str | None, visit_date: datetime) -> CommunityContact | None:
    """
    Return the existing CommunityContact for this person on this calendar day,
    or None if no match is found.
    """
    candidates = session.exec(
        select(CommunityContact).where(
            CommunityContact.first_name == first_name,
            CommunityContact.last_name == last_name,
        )
    ).all()

    for record in candidates:
        if record.visited_at.date() == visit_date.date():
            return record
    return None


def merge_into(existing: CommunityContact, row_email: str, row_pronouns: str | None,
               row_age_range: str | None, row_postal: str | None, row_how_heard: str | None,
               row_reason: str | None, row_opt_updates: bool, row_opt_volunteer: bool,
               row_opt_teaching: bool) -> bool:
    """
    Merge data from a duplicate CSV row into an existing record. Only fills in
    blank fields and upgrades opt-in flags from False to True — never overwrites
    data that is already present. Returns True if any field was changed.
    """
    changed = False

    if not existing.email and row_email:
        existing.email = row_email
        changed = True
    if not existing.pronouns and row_pronouns:
        existing.pronouns = row_pronouns
        changed = True
    if not existing.age_range and row_age_range:
        existing.age_range = row_age_range
        changed = True
    if not existing.postal_code and row_postal:
        existing.postal_code = row_postal
        changed = True
    if not existing.how_heard and row_how_heard:
        existing.how_heard = row_how_heard
        changed = True
    if not existing.other_reason and row_reason:
        existing.other_reason = row_reason
        changed = True
    if not existing.opt_in_updates and row_opt_updates:
        existing.opt_in_updates = True
        changed = True
    if not existing.opt_in_volunteer and row_opt_volunteer:
        existing.opt_in_volunteer = True
        changed = True
    if not existing.opt_in_teaching and row_opt_teaching:
        existing.opt_in_teaching = True
        changed = True

    return changed


def import_csv(csv_path: Path) -> None:
    """Read the CSV file and upsert each row into the CommunityContact table."""

    if not csv_path.exists():
        print(f"Error: CSV file not found at: {csv_path}")
        sys.exit(1)

    inserted = 0
    skipped = 0
    errors = 0

    # Open with utf-8-sig to handle the BOM character present in some exports
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        with Session(engine) as session:
            for line_num, row in enumerate(reader, start=2):  # line 1 is the header
                try:
                    raw_date = row.get(COL_DATE, "").strip()
                    if not raw_date:
                        print(f"  Line {line_num}: skipping - missing date.")
                        skipped += 1
                        continue

                    visit_date = parse_date(raw_date)

                    first_name = (row.get(COL_FIRST_NAME) or "").strip().title()
                    last_name = normalise_str(row.get(COL_LAST_NAME))
                    if last_name:
                        last_name = last_name.title()

                    if not first_name:
                        print(f"  Line {line_num}: skipping - missing first name.")
                        skipped += 1
                        continue

                    connect_cell = row.get(COL_CONNECT, "") or ""
                    opt_in_updates, opt_in_volunteer, opt_in_teaching = parse_opt_ins(connect_cell)

                    raw_email = normalise_str(row.get(COL_EMAIL))
                    email = raw_email if raw_email else ""

                    existing = find_existing(session, first_name, last_name, visit_date)

                    if existing:
                        # Merge missing data from this row into the existing record
                        changed = merge_into(
                            existing,
                            row_email=email,
                            row_pronouns=normalise_str(row.get(COL_PRONOUNS)),
                            row_age_range=normalise_str(row.get(COL_AGE_RANGE)),
                            row_postal=normalise_str(row.get(COL_POSTAL)),
                            row_how_heard=normalise_str(row.get(COL_HOW_HEARD)),
                            row_reason=normalise_str(row.get(COL_REASON)),
                            row_opt_updates=opt_in_updates,
                            row_opt_volunteer=opt_in_volunteer,
                            row_opt_teaching=opt_in_teaching,
                        )
                        if changed:
                            session.add(existing)
                            session.commit()
                            print(
                                f"  Line {line_num}: merged duplicate - "
                                f"{first_name} {last_name or ''} (id={existing.id}) updated with new data."
                            )
                        else:
                            print(
                                f"  Line {line_num}: skipping duplicate - "
                                f"{first_name} {last_name or ''} on {visit_date.date()} (no new data)."
                            )
                        skipped += 1
                        continue

                    contact = CommunityContact(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        pronouns=normalise_str(row.get(COL_PRONOUNS)),
                        age_range=normalise_str(row.get(COL_AGE_RANGE)),
                        postal_code=normalise_str(row.get(COL_POSTAL)),
                        how_heard=normalise_str(row.get(COL_HOW_HEARD)),
                        other_reason=normalise_str(row.get(COL_REASON)),
                        visited_at=visit_date,
                        opt_in_updates=opt_in_updates,
                        opt_in_volunteer=opt_in_volunteer,
                        opt_in_teaching=opt_in_teaching,
                        # These records are walk-in contacts, not community tours
                        is_community_tour=False,
                    )

                    session.add(contact)
                    session.commit()
                    session.refresh(contact)

                    print(
                        f"  Line {line_num}: imported {first_name} {last_name or ''} "
                        f"(id={contact.id}) visited {visit_date.date()}."
                    )
                    inserted += 1

                except Exception as exc:
                    print(f"  Line {line_num}: ERROR - {exc}")
                    session.rollback()
                    errors += 1

    print()
    print(f"Import complete: {inserted} inserted, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    # Allow an optional path argument; default to community_night_data.csv
    if len(sys.argv) > 1:
        target_csv = Path(sys.argv[1]).resolve()
    else:
        target_csv = project_root / "scripts" / "community_night_data.csv"

    print(f"Importing community contacts from: {target_csv}")
    print(f"Target database: {db_path}")
    print()

    import_csv(target_csv)
