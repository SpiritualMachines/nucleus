"""Authentication and password management."""

from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from core.database import engine
from core.models import User, UserPreference
from core.security import get_password_hash, verify_password
from core.services.settings import get_setting

__all__ = [
    "authenticate_user",
    "update_user_password",
]


def authenticate_user(email: str, password: str) -> Optional[User]:
    """
    Authenticates by email and password. Enforces login_attempt_limit if set
    (0 = unlimited). Failed attempt counts are stored as UserPreference entries so
    no schema change is required on the User table. On successful login the attempt
    counter is reset. Raises ValueError with a lockout message when the account is
    locked; returns None on invalid credentials without revealing which field failed.
    """
    limit = int(get_setting("login_attempt_limit", "0"))

    with Session(engine) as session:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        if not user:
            return None

        acct = user.account_number

        # Check whether the account is currently locked
        if limit > 0:
            locked_until_str = session.exec(
                select(UserPreference)
                .where(UserPreference.user_account_number == acct)
                .where(UserPreference.key == "login_locked_until")
            ).first()
            if locked_until_str and locked_until_str.value:
                try:
                    locked_until = datetime.fromisoformat(locked_until_str.value)
                    if datetime.now() < locked_until:
                        raise ValueError(
                            "Account locked due to too many failed attempts. "
                            "Please contact staff."
                        )
                    else:
                        # Lock window has expired — clear it
                        locked_until_str.value = ""
                        session.add(locked_until_str)
                        session.commit()
                except ValueError as exc:
                    # Re-raise lockout messages; swallow datetime parse errors
                    if "Account locked" in str(exc):
                        raise

        if not verify_password(password, user.password_hash):
            # Increment failure counter when a limit is configured
            if limit > 0:
                attempts_row = session.exec(
                    select(UserPreference)
                    .where(UserPreference.user_account_number == acct)
                    .where(UserPreference.key == "failed_login_attempts")
                ).first()
                attempts = int(attempts_row.value) + 1 if attempts_row else 1

                if attempts_row:
                    attempts_row.value = str(attempts)
                    session.add(attempts_row)
                else:
                    session.add(
                        UserPreference(
                            user_account_number=acct,
                            key="failed_login_attempts",
                            value=str(attempts),
                        )
                    )

                if attempts >= limit:
                    # Lock the account for 30 minutes
                    lock_expiry = (datetime.now() + timedelta(minutes=30)).isoformat()
                    lock_row = session.exec(
                        select(UserPreference)
                        .where(UserPreference.user_account_number == acct)
                        .where(UserPreference.key == "login_locked_until")
                    ).first()
                    if lock_row:
                        lock_row.value = lock_expiry
                        session.add(lock_row)
                    else:
                        session.add(
                            UserPreference(
                                user_account_number=acct,
                                key="login_locked_until",
                                value=lock_expiry,
                            )
                        )

                session.commit()
            return None

        # Successful login — clear failure tracking
        if limit > 0:
            for key in ("failed_login_attempts", "login_locked_until"):
                row = session.exec(
                    select(UserPreference)
                    .where(UserPreference.user_account_number == acct)
                    .where(UserPreference.key == key)
                ).first()
                if row:
                    row.value = ""
                    session.add(row)
            session.commit()

        return user


# --- Password Management ---


def update_user_password(acct_num: int, old_password: str, new_password: str):
    """
    Verifies the user's current password first, then enforces the min_password_length
    setting, and finally replaces the hash. Old password is checked before new password
    policy so the caller cannot use policy errors to probe whether the current password
    is correct.
    """
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            raise ValueError("User not found.")
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Current password is incorrect.")

        min_len = int(get_setting("min_password_length", "8"))
        if len(new_password) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters.")

        user.password_hash = get_password_hash(new_password)
        session.add(user)
        session.commit()
