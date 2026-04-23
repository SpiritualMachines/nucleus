"""Day pass issuance and history."""

from datetime import datetime
from typing import List

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import DayPass

__all__ = [
    "get_user_day_passes",
    "add_day_pass",
]


def get_user_day_passes(acct_num: int) -> List[DayPass]:
    """Returns all day pass records for the given user, newest first."""
    with Session(engine) as session:
        stmt = (
            select(DayPass)
            .where(DayPass.user_account_number == acct_num)
            .order_by(desc(DayPass.date))
        )
        return session.exec(stmt).all()


def add_day_pass(acct_num: int, date: datetime, description: str):
    """Creates a new day pass activation record for the given user."""
    with Session(engine) as session:
        day_pass = DayPass(
            user_account_number=acct_num,
            date=date,
            description=description,
        )
        session.add(day_pass)
        session.commit()
