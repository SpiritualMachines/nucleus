"""Feedback CRUD operations."""

from typing import List, Optional

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import Feedback

__all__ = [
    "get_all_feedback",
    "get_feedback_by_id",
    "submit_feedback",
    "update_feedback_response",
    "delete_feedback",
]


def get_all_feedback() -> List[Feedback]:
    with Session(engine) as session:
        return session.exec(
            select(Feedback).order_by(desc(Feedback.submitted_at))
        ).all()


def get_feedback_by_id(fb_id: int) -> Optional[Feedback]:
    with Session(engine) as session:
        return session.get(Feedback, fb_id)


def submit_feedback(acct, fname, lname, urgent, comment):
    with Session(engine) as session:
        fb = Feedback(
            user_account_number=acct,
            first_name=fname,
            last_name=lname,
            urgent=urgent,
            comment=comment,
        )
        session.add(fb)
        session.commit()


def update_feedback_response(fb_id: int, response: str):
    with Session(engine) as session:
        fb = session.get(Feedback, fb_id)
        if fb:
            fb.admin_response = response
            session.add(fb)
            session.commit()


def delete_feedback(feedback_id: int):
    """Deletes a feedback entry."""
    with Session(engine) as session:
        fb = session.get(Feedback, feedback_id)
        if fb:
            session.delete(fb)
            session.commit()
