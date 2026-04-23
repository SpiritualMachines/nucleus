from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

# Using SQLite as requested
sqlite_file_name = "hackspace.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# check_same_thread=False is needed for Textual because it runs on an async loop
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(engine)


def _verify_and_add_column(session: Session, table: str, column: str, col_type: str):
    """
    Idempotent column migration helper.
    Adds the column to the table only if it does not already exist.
    Skips silently if the table itself does not exist yet (will be created by
    create_db_and_tables).
    """
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return

    existing = [
        row.name
        for row in session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    ]
    if column not in existing:
        session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        session.commit()


def _verify_and_drop_column(session: Session, table: str, column: str):
    """
    Idempotent column removal helper.
    Drops the column from the table only if it currently exists.
    Skips silently if the table or column does not exist.
    Requires SQLite 3.35.0+ (ships with Python 3.12+).
    """
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return

    existing = [
        row.name
        for row in session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    ]
    if column in existing:
        session.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
        session.commit()


def _migrate_daypasses_from_usercredits(session: Session):
    """Moves legacy daypass rows from usercredits into the dedicated daypass table.

    Prior to this migration, day pass activations were stored in the usercredits
    table with credit_debit='daypass'. The new daypass table is a cleaner home.
    This function is idempotent — rows are removed from usercredits after being
    copied, so repeated runs only process rows that have not yet been migrated.
    """
    inspector = inspect(engine)
    if "usercredits" not in inspector.get_table_names():
        return
    if "daypass" not in inspector.get_table_names():
        return

    legacy_rows = session.execute(
        text(
            "SELECT id, user_account_number, date, description FROM usercredits WHERE credit_debit = 'daypass'"
        )
    ).fetchall()

    if not legacy_rows:
        return

    for row in legacy_rows:
        session.execute(
            text(
                "INSERT INTO daypass (user_account_number, date, description)"
                " VALUES (:acct, :date, :desc)"
            ),
            {"acct": row[1], "date": row[2], "desc": row[3]},
        )
        session.execute(
            text("DELETE FROM usercredits WHERE id = :id"),
            {"id": row[0]},
        )

    session.commit()


def _normalise_user_roles(session: Session):
    """
    Fixes any user rows whose role value does not match a current UserRole enum
    member. This can happen when roles are renamed or removed between versions,
    or when SQLAlchemy stored the enum NAME ('ADMIN') instead of its value ('admin').

    Case-insensitive matches are corrected to the canonical lowercase value.
    Truly unrecognised values are set to 'community' as the safest default.
    """
    inspector = inspect(engine)
    if "user" not in inspector.get_table_names():
        return

    valid_roles = {"admin", "staff", "member", "community"}

    # Find rows where the role is NULL or not already a valid lowercase value.
    bad_rows = session.execute(
        text(
            "SELECT account_number, role FROM user "
            "WHERE role NOT IN (:r1, :r2, :r3, :r4) OR role IS NULL"
        ),
        {"r1": "admin", "r2": "staff", "r3": "member", "r4": "community"},
    ).fetchall()

    if bad_rows:
        for row in bad_rows:
            # Preserve the role if it is just a case mismatch (e.g. "Admin", "STAFF")
            lowered = row.role.lower().strip() if row.role else None
            new_role = lowered if lowered in valid_roles else "community"

            session.execute(
                text("UPDATE user SET role = :new_role WHERE account_number = :acct"),
                {"new_role": new_role, "acct": row.account_number},
            )
        session.commit()
        print(
            f"[Migration] Normalised {len(bad_rows)} user(s) with non-standard role values"
        )


def run_migrations():
    """
    Applies all incremental schema changes to an existing database.
    Safe to call on every launch — each operation is idempotent.

    Rules:
    - Register every new column added to an EXISTING table with _verify_and_add_column.
    - Brand new tables (e.g. UserPreference, AppSetting) do NOT need entries here;
      create_db_and_tables() creates them via SQLModel.metadata.create_all(), which is
      itself idempotent. Only add entries below when columns are added to tables that
      already exist in production databases.
    """
    with Session(engine) as session:
        # user table
        _verify_and_add_column(session, "user", "role", "VARCHAR")
        _verify_and_add_column(session, "user", "interests", "TEXT")
        _verify_and_add_column(session, "user", "skills_training", "TEXT")
        _verify_and_add_column(session, "user", "safety_accreditations", "TEXT")
        _verify_and_add_column(session, "user", "warnings", "TEXT")
        _verify_and_add_column(session, "user", "account_comments", "TEXT")

        # safetytraining table
        _verify_and_add_column(session, "safetytraining", "whmis", "INTEGER DEFAULT 0")

        # feedback table
        _verify_and_add_column(session, "feedback", "admin_response", "TEXT")

        # usercredits table
        _verify_and_add_column(session, "usercredits", "description", "TEXT")
        _verify_and_add_column(session, "usercredits", "credits", "FLOAT")

        # activemembership table
        _verify_and_add_column(session, "activemembership", "description", "TEXT")

        # spaceattendance table
        _verify_and_add_column(session, "spaceattendance", "visit_type", "VARCHAR")

        # communitycontact table
        _verify_and_add_column(session, "communitycontact", "staff_name", "TEXT")
        _verify_and_add_column(session, "communitycontact", "pronouns", "VARCHAR")
        _verify_and_add_column(session, "communitycontact", "age_range", "VARCHAR")
        _verify_and_add_column(session, "communitycontact", "postal_code", "VARCHAR")
        _verify_and_add_column(session, "communitycontact", "how_heard", "VARCHAR")
        _verify_and_add_column(
            session, "communitycontact", "opt_in_updates", "INTEGER DEFAULT 0"
        )
        _verify_and_add_column(
            session, "communitycontact", "opt_in_volunteer", "INTEGER DEFAULT 0"
        )
        _verify_and_add_column(
            session, "communitycontact", "opt_in_teaching", "INTEGER DEFAULT 0"
        )

        # appsetting table — is_sensitive marks fields the UI must never display again
        _verify_and_add_column(
            session, "appsetting", "is_sensitive", "INTEGER DEFAULT 0"
        )

        # userpreference table — new table introduced for per-user preference storage.
        # No column migrations needed; create_db_and_tables() creates the whole table.

        # squaretransaction table — new table for Point of Sale transaction records.
        # No column migrations needed; create_db_and_tables() creates the whole table.

        # producttier table — new table for reusable membership/day pass tier templates.
        # No column migrations needed; create_db_and_tables() creates the whole table.

        # posconfig table — new table for Square Terminal API configuration.
        # No column migrations needed for the initial table creation.
        # Separate sandbox and production token columns added after initial release.
        _verify_and_add_column(
            session, "posconfig", "square_access_token_sandbox", "VARCHAR DEFAULT ''"
        )
        _verify_and_add_column(
            session, "posconfig", "square_access_token_production", "VARCHAR DEFAULT ''"
        )
        _verify_and_add_column(
            session, "posconfig", "square_push_cash_enabled", "BOOLEAN DEFAULT 0"
        )
        # Remove the legacy single-token column — replaced by the per-environment fields.
        _verify_and_drop_column(session, "posconfig", "square_access_token")

        # squaretransaction table — refund tracking and staff attribution fields.
        _verify_and_add_column(session, "squaretransaction", "processed_by", "VARCHAR")
        _verify_and_add_column(session, "squaretransaction", "refund_status", "VARCHAR")
        _verify_and_add_column(session, "squaretransaction", "refund_reason", "TEXT")
        _verify_and_add_column(session, "squaretransaction", "refunded_at", "DATETIME")
        _verify_and_add_column(session, "squaretransaction", "refunded_by", "VARCHAR")

        # user table — Square subscription tracking fields added for recurring billing.
        _verify_and_add_column(session, "user", "square_customer_id", "VARCHAR")
        _verify_and_add_column(session, "user", "square_subscription_id", "VARCHAR")
        _verify_and_add_column(session, "user", "square_subscription_status", "VARCHAR")
        _verify_and_add_column(
            session, "user", "square_subscription_checked_at", "DATETIME"
        )

        # storageunit and storageassignment tables — new tables for member storage tracking.
        # No column migrations needed for new tables; create_db_and_tables() handles them.
        # Column renames and additions for existing storageassignment records:
        _verify_and_add_column(session, "storageassignment", "charge_type", "VARCHAR")
        _verify_and_add_column(session, "storageassignment", "charge_notes", "TEXT")

        # inventoryitem table — new table for POS transaction cart items.
        # No column migrations needed; create_db_and_tables() creates the table.

        # daypass table — new dedicated table replacing the daypass rows that were
        # previously stored in usercredits with credit_debit='daypass'.
        # No column migrations needed; create_db_and_tables() creates the whole table.

        # Data migration: move existing daypass rows out of usercredits into the
        # dedicated daypass table. Runs every launch but is idempotent — rows are
        # deleted from usercredits after insertion so they are never copied twice.
        _migrate_daypasses_from_usercredits(session)

        # Data migration: normalise any legacy role values that are not in the
        # current UserRole enum (admin, staff, member, community). Accounts with
        # unrecognised roles are set to "community" so the UI does not crash when
        # staff try to edit them.
        _normalise_user_roles(session)
