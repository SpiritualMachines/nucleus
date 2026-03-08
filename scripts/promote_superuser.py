import os
import sys
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
# This ensures the script finds 'hackspace.db' in the root folder.
os.chdir(project_root)

# 3. VERIFY DB EXISTENCE (Safety Check)
db_path = project_root / "hackspace.db"
if not db_path.exists():
    print(f"❌ Error: Database file not found at: {db_path}")
    print(
        "   Please run the main application (hack_daemon.py) first to initialize the database."
    )
    sys.exit(1)
else:
    print(f"📂 Database found at: {db_path}")

# -------------------------

from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from core.models import User, UserRole  # noqa: E402


def promote_user(email: str):
    with Session(engine) as session:
        # 1. Find the user
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found.")
            print("   Did you complete the registration form in the app?")
            return

        # 2. Promote them
        print(
            f"Found User: {user.first_name} {user.last_name} (Current Role: {user.role})"
        )

        user.role = UserRole.ADMIN  # Set to Admin
        user.is_active = True  # Activate the account
        user.id_checked = True  # Mark ID as checked

        session.add(user)
        session.commit()
        session.refresh(user)

        print(f"✅ SUCCESS! User '{email}' is now an ACTIVE ADMIN.")
        print("   You may now log in via the TUI.")


if __name__ == "__main__":
    print(f"🔧 Running from Project Root: {os.getcwd()}")
    # Change this to the email you just registered with!
    target_email = input("Enter the email you registered with: ")
    promote_user(target_email)
