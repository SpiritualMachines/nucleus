"""Day pass issuance and history."""

from datetime import datetime
from typing import List

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import UserCredits

__all__ = [
    "get_user_day_passes",
    "add_day_pass",
]


def get_user_day_passes(acct_num: int) -> List[UserCredits]:
    # This expects an object with .date and .description
    with Session(engine) as session:
        # Returning UserCredits that are flagged as 'daypass'
        stmt = (
            select(UserCredits)
            .where(UserCredits.user_account_number == acct_num)
            .where(UserCredits.credit_debit == "daypass")
            .order_by(desc(UserCredits.date))
        )
        return session.exec(stmt).all()


def add_day_pass(acct_num: int, date: datetime, description: str):
    with Session(engine) as session:
        # Store as a credit record with special type
        credit = UserCredits(
            user_account_number=acct_num,
            credits=0.0,
            description=description,
            credit_debit="daypass",
            date=date,
        )
        session.add(credit)
        session.commit()
