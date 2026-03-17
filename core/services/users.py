"""User registration, search, approval, and profile management."""

from datetime import datetime
from random import randint
from typing import List, Optional, Union

from sqlalchemy import or_
from sqlmodel import Session, select

from core.database import engine
from core.models import User, UserRole
from core.security import get_password_hash
from core.services.settings import get_setting

__all__ = [
    "generate_account_number",
    "get_users",
    "get_pending_users",
    "search_users",
    "get_user_by_account",
    "approve_user",
    "register_user",
    "register_verified_user",
    "update_user_details",
]


# --- Helper to generate ID ---
def generate_account_number(session: Session) -> int:
    """
    Generates a unique account number with the format:
    [9 Random Digits] + [Source: 1] + [Month: MM] + [Year: YY]
    Total Length: 14 Digits.
    """
    now = datetime.now()
    month_str = now.strftime("%m")  # 2 digit month
    year_str = now.strftime("%y")  # 2 digit year
    source_id = "1"  # Source ID for this app

    while True:
        # Generate random 9 digit int
        random_part = randint(100000000, 999999999)

        # Construct: RRRRRRRRR + 1 + MM + YY
        candidate_str = f"{random_part}{source_id}{month_str}{year_str}"
        acc_num = int(candidate_str)

        # Verify uniqueness
        existing = session.get(User, acc_num)
        if not existing:
            return acc_num


# --- User Management ---


def get_users(roles: List[Union[UserRole, str]] = None) -> List[User]:
    """
    Fetches users, optionally filtered by a list of roles.
    Accepts both UserRole Enums and raw strings.
    """
    with Session(engine) as session:
        if roles:
            # Robust filtering: generate variations to catch case mismatches
            safe_roles = []
            for r in roles:
                val = r.value if hasattr(r, "value") else str(r)
                # Add lowercase, uppercase, and title case to be absolutely sure
                safe_roles.append(val.lower())
                safe_roles.append(val.upper())
                safe_roles.append(val.title())
                safe_roles.append(val)  # Add exact value just in case

            # Remove duplicates
            safe_roles = list(set(safe_roles))

            # Use the IN clause with the safe string list
            statement = select(User).where(User.role.in_(safe_roles))
        else:
            statement = select(User)

        return session.exec(statement).all()


def get_pending_users() -> List[User]:
    with Session(engine) as session:
        statement = select(User).where(User.is_active.is_(False))
        return session.exec(statement).all()


def search_users(query_str: str) -> List[User]:
    with Session(engine) as session:
        query_str = f"%{query_str}%"
        statement = select(User).where(
            or_(
                User.first_name.ilike(query_str),
                User.last_name.ilike(query_str),
                User.email.ilike(query_str),
            )
        )
        return session.exec(statement).all()


def get_user_by_account(acct_num: int) -> Optional[User]:
    with Session(engine) as session:
        return session.get(User, acct_num)


def approve_user(admin_acct: int, target_acct: int):
    with Session(engine) as session:
        # Verify admin
        admin = session.get(User, admin_acct)
        # Check against both string and enum for robustness
        role_str = (
            str(admin.role).lower()
            if isinstance(admin.role, str)
            else admin.role.value.lower()
        )

        if role_str not in ["admin", "staff"]:
            raise PermissionError("Only Staff/Admin can approve users.")

        target = session.get(User, target_acct)
        if target:
            target.is_active = True
            # Defaults to Community on approval unless manually changed
            target_role_str = (
                str(target.role).lower()
                if isinstance(target.role, str)
                else target.role.value.lower()
            )

            if target_role_str != "member":
                target.role = UserRole.COMMUNITY

            session.add(target)
            session.commit()


def register_user(user_data: dict, password: str) -> User:
    """
    Standard registration (pending approval). Enforces the min_password_length
    setting before creating the account.
    """
    min_len = int(get_setting("min_password_length", "8"))
    if len(password) < min_len:
        raise ValueError(f"Password must be at least {min_len} characters.")

    with Session(engine) as session:
        # Check email unique
        existing = session.exec(
            select(User).where(User.email == user_data["email"])
        ).first()
        if existing:
            raise ValueError("Email already registered.")

        # Create User
        acct_num = generate_account_number(session)
        # Default new users to COMMUNITY role (string)
        new_user = User(
            account_number=acct_num,
            password_hash=get_password_hash(password),
            role=UserRole.COMMUNITY,
            is_active=False,  # Pending approval
            **user_data,
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user


def register_verified_user(user_data: dict, password: str) -> User:
    """
    Staff-assisted registration (Active immediately, ID checked). Enforces the
    min_password_length setting before creating the account.
    """
    min_len = int(get_setting("min_password_length", "8"))
    if len(password) < min_len:
        raise ValueError(f"Password must be at least {min_len} characters.")

    with Session(engine) as session:
        # Check email unique
        existing = session.exec(
            select(User).where(User.email == user_data["email"])
        ).first()
        if existing:
            raise ValueError("Email already registered.")

        # Create User
        acct_num = generate_account_number(session)

        # Remove conflicting keys from user_data if present
        # This prevents "got multiple values for keyword argument" error
        user_data.pop("role", None)
        user_data.pop("is_active", None)
        user_data.pop("id_checked", None)

        # Override fields for verified status
        new_user = User(
            account_number=acct_num,
            password_hash=get_password_hash(password),
            role=UserRole.COMMUNITY,
            is_active=True,  # Active immediately
            id_checked=True,  # Verified in person
            **user_data,
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user


def update_user_details(acct_num: int, data: dict) -> User:
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            raise ValueError("User not found")

        for key, value in data.items():
            setattr(user, key, value)

        session.add(user)
        session.commit()
        session.refresh(user)
        return user
