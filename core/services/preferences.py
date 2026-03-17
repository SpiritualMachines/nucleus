"""Per-user preference storage backed by the UserPreference table."""

from sqlmodel import Session, select

from core.database import engine
from core.models import UserPreference

__all__ = [
    "get_user_preference",
    "set_user_preference",
    "get_all_user_preferences",
]


def get_user_preference(acct_num: int, key: str, default: str = "") -> str:
    """
    Returns the stored preference value for a given user and key.
    Returns default if the preference has not been set for that user.
    """
    with Session(engine) as session:
        pref = session.exec(
            select(UserPreference)
            .where(UserPreference.user_account_number == acct_num)
            .where(UserPreference.key == key)
        ).first()
        return pref.value if pref else default


def set_user_preference(acct_num: int, key: str, value: str) -> None:
    """
    Creates or updates a single user preference. Uses upsert logic consistent
    with set_setting so behaviour is uniform across the application.
    """
    with Session(engine) as session:
        pref = session.exec(
            select(UserPreference)
            .where(UserPreference.user_account_number == acct_num)
            .where(UserPreference.key == key)
        ).first()
        if pref:
            pref.value = value
        else:
            pref = UserPreference(user_account_number=acct_num, key=key, value=value)
        session.add(pref)
        session.commit()


def get_all_user_preferences(acct_num: int) -> dict:
    """
    Returns all preferences for a given user as a plain dict keyed by preference key.
    Avoids returning ORM objects so callers remain session-independent.
    """
    with Session(engine) as session:
        prefs = session.exec(
            select(UserPreference).where(UserPreference.user_account_number == acct_num)
        ).all()
        return {p.key: p.value for p in prefs}
