import getpass
import os
import sys
from pathlib import Path

# --- ROBUST PATH SETUP ---
# This ensures we can import from 'core' regardless of where the script is run from.
current_file = Path(__file__).resolve()

if current_file.parent.name in ("scripts", "core"):
    project_root = current_file.parent.parent
else:
    project_root = current_file.parent

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Switch to project root so database file is found correctly
os.chdir(project_root)

# -------------------------

from sqlmodel import Session, select  # noqa: E402

from core.database import create_db_and_tables, engine  # noqa: E402
from core.models import User, UserRole  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from core.services import generate_account_number  # noqa: E402


def create_initial_admin():
    print(f"🔧 Target Database: {project_root / 'hackspace.db'}")

    # Ensure tables exist (handles case where DB file exists but is empty)
    create_db_and_tables()

    print("\n--- Create Initial Admin User ---")

    # Prompt for Email
    while True:
        email = input("Enter Admin Email: ").strip()
        if email:
            break
        print("Error: Email cannot be empty.")

    # Prompt for Password with Confirmation
    while True:
        password = getpass.getpass("Enter Admin Password: ")
        if not password:
            print("Error: Password cannot be empty.")
            continue

        confirm = getpass.getpass("Confirm Password:     ")

        if password == confirm:
            break
        print("❌ Passwords do not match. Try again.\n")

    with Session(engine) as session:
        # 1. Check if user already exists
        statement = select(User).where(User.email == email)
        existing_user = session.exec(statement).first()

        if existing_user:
            print(f"\n⚠️  User '{email}' already exists.")
            print("   Updating existing user to ADMIN status and resetting password...")

            existing_user.role = UserRole.ADMIN
            existing_user.is_active = True
            existing_user.id_checked = True
            existing_user.banned = False
            existing_user.password_hash = get_password_hash(password)

            session.add(existing_user)
            session.commit()
            print("✅ Updated successfully.")
            return

        # 2. Create New Admin User
        print(f"\nCreating new user: {email} ...")

        # We need to fill required fields, using dummy data for the address/contact info
        new_account_number = generate_account_number(session)

        admin_user = User(
            account_number=new_account_number,
            email=email,
            password_hash=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
            id_checked=True,
            first_name="System",
            last_name="Admin",
            phone="555-0199",
            # Dummy Address Info
            street_address="123 Root Access Rd",
            city="Server City",
            province="ON",
            postal_code="A1A 1A1",
            # Dummy Emergency Info
            emergency_first_name="System",
            emergency_last_name="Operator",
            emergency_phone="555-9111",
            # Agreements
            policies_agreed=True,
            code_of_conduct_agreed=True,
        )

        session.add(admin_user)
        session.commit()

        print("-------------------------------------------------------")
        print("✅ SUCCESS: Admin User Created")
        print(f"   Account #: {new_account_number}")
        print(f"   Email:     {email}")
        print("-------------------------------------------------------")


if __name__ == "__main__":
    create_initial_admin()
