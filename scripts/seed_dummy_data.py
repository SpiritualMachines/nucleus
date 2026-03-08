import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- ROBUST PATH SETUP ---
# Get the absolute path of this script
current_file = Path(__file__).resolve()

# Determine Project Root
# If we are in 'scripts/' or 'core/', the root is two levels up.
if current_file.parent.name in ("scripts", "core"):
    project_root = current_file.parent.parent
else:
    # Otherwise, assume we are already in the project root
    project_root = current_file.parent

# 1. Add the project root to Python's system path so we can import 'core'
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# 2. CRITICAL: Switch working directory to project root
os.chdir(project_root)

# 3. VERIFY DB EXISTENCE
db_path = project_root / "hackspace.db"
if not db_path.exists():
    print(f"❌ Error: Database file not found at: {db_path}")
    print("   Please run the main application first to initialize the database.")
    sys.exit(1)

# -------------------------

from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from core.models import SafetyTraining, SpaceAttendance, User, UserCredits, UserRole  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from core.services import generate_account_number  # noqa: E402


def generate_attendance_history(session: Session, user: User):
    """Generates random sign-in/out records for the past 60 days."""

    # 50% chance a user has been active recently
    if random.random() > 0.5:
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    current_date = start_date

    while current_date < end_date:
        # 30% chance to visit on any given day
        if random.random() < 0.3:
            # Pick a random start time between 10 AM and 8 PM
            hour = random.randint(10, 20)
            minute = random.randint(0, 59)
            sign_in = current_date.replace(hour=hour, minute=minute, second=0)

            # Stay for 1 to 4 hours
            duration = random.randint(1, 4)
            sign_out = sign_in + timedelta(hours=duration)

            # Don't create future records
            if sign_out > datetime.now():
                break

            record = SpaceAttendance(
                user_account_number=user.account_number,
                sign_in_time=sign_in,
                sign_out_time=sign_out,
            )
            session.add(record)

        current_date += timedelta(days=1)


def create_dummy_user(
    session: Session,
    email: str,
    role: UserRole,
    first_name: str,
    last_name: str,
    active: bool = True,
):
    # 1. Check if exists
    statement = select(User).where(User.email == email)
    existing = session.exec(statement).first()
    if existing:
        return existing

    # 2. Generate Data
    # Password for everyone is "test" (as requested)
    hashed_pw = get_password_hash("test")

    user = User(
        email=email,
        password_hash=hashed_pw,
        account_number=generate_account_number(session),
        role=role,
        is_active=active,
        id_checked=active,
        # Personal Info
        first_name=first_name,
        last_name=last_name,
        date_of_birth=datetime(1990, 1, 1),
        phone=f"555-{random.randint(1000, 9999)}",
        # Address
        street_address=f"{random.randint(1, 999)} Dummy Lane",
        city="Testville",
        province="ON",
        postal_code="H0H 0H0",
        # Emergency
        emergency_first_name="Emergency",
        emergency_last_name="Contact",
        emergency_phone="555-9999",
        # Details
        allergies="None",
        health_concerns="None",
        interests="Coding, CNC, Woodworking",
        skills_training="Python, Welding",
        # Agreements
        policies_agreed=True,
        code_of_conduct_agreed=True,
        joined_date=datetime.now() - timedelta(days=random.randint(10, 365)),
    )

    # 3. Create Related Records
    safety = SafetyTraining(user_account_number=user.account_number)
    credits = UserCredits(user_account_number=user.account_number)

    # 4. Save
    session.add(user)
    session.add(safety)
    session.add(credits)

    # 5. Generate History
    generate_attendance_history(session, user)

    session.commit()
    return user


def seed_data():
    print(f"🌱 Seeding MASSIVE Dummy Data into: {db_path} ...")

    with Session(engine) as session:
        # 1. Core Accounts
        create_dummy_user(session, "test@admin.ca", UserRole.ADMIN, "Alice", "Admin")
        create_dummy_user(session, "test@staff.ca", UserRole.STAFF, "Steve", "Staff")
        create_dummy_user(session, "test@member.ca", UserRole.MEMBER, "Mike", "Member")
        create_dummy_user(
            session, "test@community.ca", UserRole.COMMUNITY, "Chris", "Community"
        )

        print("✅ Core Accounts Created.")

        # 2. Generate 100 Random Users
        roles = (
            [UserRole.MEMBER] * 60 + [UserRole.COMMUNITY] * 30 + [UserRole.STAFF] * 10
        )
        first_names = [
            "James",
            "Mary",
            "John",
            "Patricia",
            "Robert",
            "Jennifer",
            "Michael",
            "Linda",
            "William",
            "Elizabeth",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
        ]

        for i, role in enumerate(roles):
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            email = f"user{i}_{fn.lower()}@test.com"

            # 10% chance user is inactive/pending
            is_active = random.random() > 0.1

            create_dummy_user(session, email, role, fn, ln, active=is_active)

            if i % 10 == 0:
                print(f"   ... Generated {i} users")

    print(
        "\n✨ Done! Database populated with 100+ users (password: 'test') and attendance history."
    )


if __name__ == "__main__":
    seed_data()
