"""Space sign-in/sign-out and expired membership checks."""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import or_
from sqlmodel import Session, func, select

from core.database import engine
from core.models import SpaceAttendance, User, UserRole
from core.services.settings import get_setting

__all__ = [
    "check_expired_memberships",
    "get_current_signin_count",
    "sign_in_user",
    "sign_out_user",
    "is_user_signed_in",
    "get_signed_in_users",
]


def check_expired_memberships():
    """
    Background task. Checks for ActiveMemberships that have expired and downgrades
    the user role to COMMUNITY. Respects the membership_grace_period_days setting:
    a user whose membership expired within the grace window keeps their MEMBER role
    until the window has elapsed. Falls back to zero grace days if the setting is
    unavailable (e.g. on first run before the DB is fully initialized).
    """
    try:
        grace_days = int(get_setting("membership_grace_period_days", "0"))
    except Exception:
        grace_days = 0

    with Session(engine) as session:
        now = datetime.now()
        # The effective cutoff is the current time minus the grace window.
        # Any membership whose end_date is before this cutoff is truly expired.
        cutoff = now - timedelta(days=grace_days)

        # Get all users who are currently MEMBER (check string and enum)
        statement = select(User).where(
            or_(User.role == UserRole.MEMBER, User.role == "member")
        )
        members = session.exec(statement).all()

        for user in members:
            # Check if they have any membership whose end_date is still within
            # the grace window or still active
            has_active = False
            for mem in user.memberships:
                if mem.end_date >= cutoff:
                    has_active = True
                    break

            if not has_active:
                user.role = UserRole.COMMUNITY
                session.add(user)

        session.commit()


def get_current_signin_count() -> int:
    """Returns the number of users currently signed in (no sign-out time recorded)."""
    with Session(engine) as session:
        count = session.exec(
            select(func.count(SpaceAttendance.id)).where(
                SpaceAttendance.sign_out_time.is_(None)
            )
        ).one()
        return count or 0


def sign_in_user(acct_num: int, visit_type: str = ""):
    """
    Records a space sign-in for the given account. Raises ValueError if the user is
    already signed in, or if the space has reached the max_concurrent_signins limit
    (0 means unlimited). The duplicate check runs first so an already-signed-in user
    gets the correct error message regardless of capacity.
    """
    with Session(engine) as session:
        # Prevent duplicate open sign-ins for the same user
        active = session.exec(
            select(SpaceAttendance)
            .where(SpaceAttendance.user_account_number == acct_num)
            .where(SpaceAttendance.sign_out_time.is_(None))
        ).first()

        if active:
            raise ValueError("User is already signed in.")

        # Enforce capacity limit when configured
        max_signins = int(get_setting("max_concurrent_signins", "0"))
        if max_signins > 0:
            current_count = (
                session.exec(
                    select(func.count(SpaceAttendance.id)).where(
                        SpaceAttendance.sign_out_time.is_(None)
                    )
                ).one()
                or 0
            )
            if current_count >= max_signins:
                raise ValueError(
                    f"Space is at capacity ({max_signins} sign-ins). "
                    "Please wait for someone to sign out."
                )

        new_visit = SpaceAttendance(
            user_account_number=acct_num,
            visit_type=visit_type or None,
        )
        session.add(new_visit)
        session.commit()


def sign_out_user(acct_num: int):
    with Session(engine) as session:
        active = session.exec(
            select(SpaceAttendance)
            .where(SpaceAttendance.user_account_number == acct_num)
            .where(SpaceAttendance.sign_out_time.is_(None))
        ).first()

        if not active:
            raise ValueError("User is not signed in.")

        active.sign_out_time = datetime.now()
        session.add(active)
        session.commit()


def is_user_signed_in(acct_num: int) -> bool:
    with Session(engine) as session:
        active = session.exec(
            select(SpaceAttendance)
            .where(SpaceAttendance.user_account_number == acct_num)
            .where(SpaceAttendance.sign_out_time.is_(None))
        ).first()
        return active is not None


def get_signed_in_users() -> List[User]:
    """Returns all users who currently have an open sign-in with no sign-out time."""
    with Session(engine) as session:
        statement = (
            select(User)
            .join(
                SpaceAttendance,
                SpaceAttendance.user_account_number == User.account_number,
            )
            .where(SpaceAttendance.sign_out_time.is_(None))
        )
        return session.exec(statement).all()
