"""Balance and transaction functions for consumable credits."""

from typing import List

from sqlalchemy import or_
from sqlmodel import Session, desc, func, select

from core.database import engine
from core.models import UserCredits

__all__ = [
    "get_user_transactions",
    "get_user_balance",
    "add_transaction",
]


def get_user_transactions(acct_num: int) -> List[UserCredits]:
    with Session(engine) as session:
        stmt = (
            select(UserCredits)
            .where(UserCredits.user_account_number == acct_num)
            .where(
                or_(
                    UserCredits.credit_debit == "credit",
                    UserCredits.credit_debit == "debit",
                )
            )
            .order_by(desc(UserCredits.date))
        )
        return session.exec(stmt).all()


def get_user_balance(acct_num: int) -> float:
    with Session(engine) as session:
        credits = (
            session.exec(
                select(func.sum(UserCredits.credits))
                .where(UserCredits.user_account_number == acct_num)
                .where(UserCredits.credit_debit == "credit")
            ).one()
            or 0.0
        )

        debits = (
            session.exec(
                select(func.sum(UserCredits.credits))
                .where(UserCredits.user_account_number == acct_num)
                .where(UserCredits.credit_debit == "debit")
            ).one()
            or 0.0
        )

        return float(credits - debits)


def add_transaction(acct_num: int, amount: float, type: str, desc: str):
    with Session(engine) as session:
        txn = UserCredits(
            user_account_number=acct_num,
            credits=amount,
            credit_debit=type,
            description=desc,
        )
        session.add(txn)
        session.commit()
