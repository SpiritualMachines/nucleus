"""Membership period management (excluding day passes)."""

from datetime import datetime, timedelta
from typing import List

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import ActiveMembership, User, UserRole

__all__ = [
    "add_membership",
    "get_user_memberships",
]


def add_membership(acct_num: int, months: int):
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            raise ValueError("User not found")

        start_date = datetime.now()
        end_date = start_date + (timedelta(days=30) * months)

        # Update User Role to MEMBER
        user.role = UserRole.MEMBER

        mem = ActiveMembership(
            user_account_number=acct_num, start_date=start_date, end_date=end_date
        )
        session.add(mem)
        session.add(user)
        session.commit()


def get_user_memberships(acct_num: int) -> List[ActiveMembership]:
    with Session(engine) as session:
        stmt = (
            select(ActiveMembership)
            .where(ActiveMembership.user_account_number == acct_num)
            .order_by(desc(ActiveMembership.end_date))
        )
        return session.exec(stmt).all()
