"""Community contact functions for walk-in visitor records."""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from core.database import engine
from core.models import CommunityContact

__all__ = [
    "save_community_contact",
    "get_community_contacts_report",
]


def save_community_contact(
    first_name: str,
    email: str,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    brought_in_by: Optional[str] = None,
    other_reason: Optional[str] = None,
    visited_at: Optional[datetime] = None,
    is_community_tour: bool = False,
    staff_name: Optional[str] = None,
    pronouns: Optional[str] = None,
    age_range: Optional[str] = None,
    postal_code: Optional[str] = None,
    how_heard: Optional[str] = None,
    opt_in_updates: bool = False,
    opt_in_volunteer: bool = False,
    opt_in_teaching: bool = False,
) -> CommunityContact:
    """Saves a walk-in community contact record."""
    with Session(engine) as session:
        contact = CommunityContact(
            first_name=first_name,
            email=email,
            last_name=last_name,
            phone=phone,
            brought_in_by=brought_in_by,
            other_reason=other_reason,
            visited_at=visited_at or datetime.now(),
            is_community_tour=is_community_tour,
            staff_name=staff_name,
            pronouns=pronouns,
            age_range=age_range,
            postal_code=postal_code,
            how_heard=how_heard,
            opt_in_updates=opt_in_updates,
            opt_in_volunteer=opt_in_volunteer,
            opt_in_teaching=opt_in_teaching,
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)
        return contact


# --- Community Contacts Report ---


def get_community_contacts_report(start_date: datetime, end_date: datetime) -> dict:
    """
    Fetches all community contact records whose visit falls within the given date range.
    Returns a dict with 'headers' and 'rows' ready for the standard CSV/PDF exporters.
    """
    with Session(engine) as session:
        contacts = session.exec(
            select(CommunityContact)
            .where(
                CommunityContact.visited_at >= start_date,
                CommunityContact.visited_at <= end_date,
            )
            .order_by(CommunityContact.visited_at)
        ).all()

        headers = [
            "ID",
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Brought In By",
            "Visited At",
            "Community Tour",
            "Other Reason",
            "Staff Name and Description",
        ]
        rows = [
            [
                str(c.id),
                c.first_name,
                c.last_name or "",
                c.email,
                c.phone or "",
                c.brought_in_by or "",
                str(c.visited_at),
                "Yes" if c.is_community_tour else "No",
                c.other_reason or "",
                c.staff_name or "",
            ]
            for c in contacts
        ]

    return {"headers": headers, "rows": rows}
