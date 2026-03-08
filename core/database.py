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

        # userpreference table — new table introduced for per-user preference storage.
        # No column migrations needed; create_db_and_tables() creates the whole table.
