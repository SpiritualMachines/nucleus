"""Reporting functions for period traction, people export, and daily email."""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlmodel import Session, desc, func, select

from core.database import engine
from core.models import (
    ActiveMembership,
    CommunityContact,
    Feedback,
    MembershipDues,
    SafetyTraining,
    SpaceAttendance,
    SquareTransaction,
    User,
    UserCredits,
    UserRole,
)
from core.services.settings import get_setting

__all__ = [
    "get_period_traction_report_data",
    "get_everything_people_data",
    "build_daily_report_data",
]


def get_period_traction_report_data(start_date: datetime, end_date: datetime) -> dict:
    """
    Gathers all activity data within the given date range for the Period Traction Report.
    Covers memberships active during the period, day passes, consumable transactions,
    space sign-ins, and community contact visits. All results are returned as flat lists
    of string rows ready for export, so no ORM objects escape the session.
    """
    with Session(engine) as session:
        # Memberships whose active window overlaps the report period
        mem_rows = session.exec(
            select(ActiveMembership, User)
            .join(User, ActiveMembership.user_account_number == User.account_number)
            .where(
                ActiveMembership.start_date <= end_date,
                ActiveMembership.end_date >= start_date,
            )
            .order_by(ActiveMembership.start_date)
        ).all()
        memberships = [
            [
                str(m.id),
                f"{u.first_name} {u.last_name}",
                str(u.account_number),
                str(m.start_date.date()),
                str(m.end_date.date()),
                m.description or "",
            ]
            for m, u in mem_rows
        ]

        # Day passes issued during the period
        dp_rows = session.exec(
            select(UserCredits, User)
            .join(User, UserCredits.user_account_number == User.account_number)
            .where(
                UserCredits.credit_debit == "daypass",
                UserCredits.date >= start_date,
                UserCredits.date <= end_date,
            )
            .order_by(UserCredits.date)
        ).all()
        day_passes = [
            [
                str(dp.id),
                f"{u.first_name} {u.last_name}",
                str(u.account_number),
                str(dp.date.date()),
                dp.description or "",
            ]
            for dp, u in dp_rows
        ]

        # Consumable credit and debit transactions during the period
        cons_rows = session.exec(
            select(UserCredits, User)
            .join(User, UserCredits.user_account_number == User.account_number)
            .where(
                or_(
                    UserCredits.credit_debit == "credit",
                    UserCredits.credit_debit == "debit",
                ),
                UserCredits.date >= start_date,
                UserCredits.date <= end_date,
            )
            .order_by(UserCredits.date)
        ).all()
        consumables = [
            [
                str(c.id),
                f"{u.first_name} {u.last_name}",
                str(u.account_number),
                c.credit_debit,
                f"${c.credits:.2f}",
                str(c.date.date()),
                c.description or "",
            ]
            for c, u in cons_rows
        ]

        # Space sign-in records where sign-in time falls within the period
        att_rows = session.exec(
            select(SpaceAttendance, User)
            .join(User, SpaceAttendance.user_account_number == User.account_number)
            .where(
                SpaceAttendance.sign_in_time >= start_date,
                SpaceAttendance.sign_in_time <= end_date,
            )
            .order_by(SpaceAttendance.sign_in_time)
        ).all()
        sign_ins = [
            [
                str(a.id),
                f"{u.first_name} {u.last_name}",
                str(u.account_number),
                str(a.sign_in_time),
                str(a.sign_out_time) if a.sign_out_time else "Active",
                a.visit_type or "",
            ]
            for a, u in att_rows
        ]

        # Community contact visits during the period
        contact_rows = session.exec(
            select(CommunityContact)
            .where(
                CommunityContact.visited_at >= start_date,
                CommunityContact.visited_at <= end_date,
            )
            .order_by(CommunityContact.visited_at)
        ).all()
        community_contacts = [
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
            for c in contact_rows
        ]

    return {
        "memberships": memberships,
        "day_passes": day_passes,
        "consumables": consumables,
        "sign_ins": sign_ins,
        "community_contacts": community_contacts,
    }


# --- Everything People Export ---


def get_everything_people_data() -> list[dict]:
    """
    Fetches every database record related to people, grouped into labelled sections.
    Returns a list of section dicts (title, headers, rows) compatible with the
    multi-section CSV exporter. Covers the full user profile, all membership and
    financial records, attendance, safety training, community contacts, and feedback.
    Intended as a complete data audit dump rather than a filtered report.
    """
    with Session(engine) as session:
        # Full user profiles ordered alphabetically
        users = session.exec(
            select(User).order_by(User.last_name, User.first_name)
        ).all()
        user_rows = [
            [
                str(u.account_number),
                u.first_name,
                u.last_name,
                u.email,
                str(u.role if isinstance(u.role, str) else u.role.value),
                "Yes" if u.is_active else "No",
                str(u.date_of_birth.date()) if u.date_of_birth else "",
                u.phone,
                u.street_address,
                u.city,
                u.province,
                u.postal_code,
                u.emergency_first_name,
                u.emergency_last_name,
                u.emergency_phone,
                u.allergies or "",
                u.health_concerns or "",
                "Yes" if u.policies_agreed else "No",
                "Yes" if u.code_of_conduct_agreed else "No",
                "Yes" if u.id_checked else "No",
                str(u.joined_date.date()) if u.joined_date else "",
                u.interests or "",
                u.skills_training or "",
                u.safety_accreditations or "",
                u.warnings or "",
                "Yes" if u.banned else "No",
                u.account_comments or "",
            ]
            for u in users
        ]

        # Active membership periods with linked user name
        mem_rows_raw = session.exec(
            select(ActiveMembership, User)
            .join(User, ActiveMembership.user_account_number == User.account_number)
            .order_by(User.last_name, ActiveMembership.start_date)
        ).all()
        mem_rows = [
            [
                str(m.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                str(m.start_date.date()),
                str(m.end_date.date()),
                m.description or "",
            ]
            for m, u in mem_rows_raw
        ]

        # Membership dues payments with linked user name
        dues_rows_raw = session.exec(
            select(MembershipDues, User)
            .join(User, MembershipDues.user_account_number == User.account_number)
            .order_by(User.last_name, MembershipDues.payment_date)
        ).all()
        dues_rows = [
            [
                str(d.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                d.month,
                f"${d.amount_paid:.2f}",
                str(d.payment_date.date()),
            ]
            for d, u in dues_rows_raw
        ]

        # Consumable credit and debit transactions with linked user name
        cons_rows_raw = session.exec(
            select(UserCredits, User)
            .join(User, UserCredits.user_account_number == User.account_number)
            .where(
                or_(
                    UserCredits.credit_debit == "credit",
                    UserCredits.credit_debit == "debit",
                )
            )
            .order_by(User.last_name, UserCredits.date)
        ).all()
        cons_rows = [
            [
                str(c.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                c.credit_debit,
                f"${c.credits:.2f}",
                str(c.date.date()),
                c.description or "",
            ]
            for c, u in cons_rows_raw
        ]

        # Day passes with linked user name
        dp_rows_raw = session.exec(
            select(UserCredits, User)
            .join(User, UserCredits.user_account_number == User.account_number)
            .where(UserCredits.credit_debit == "daypass")
            .order_by(User.last_name, UserCredits.date)
        ).all()
        dp_rows = [
            [
                str(dp.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                str(dp.date.date()),
                dp.description or "",
            ]
            for dp, u in dp_rows_raw
        ]

        # Space attendance records with linked user name
        att_rows_raw = session.exec(
            select(SpaceAttendance, User)
            .join(User, SpaceAttendance.user_account_number == User.account_number)
            .order_by(User.last_name, SpaceAttendance.sign_in_time)
        ).all()
        att_rows = [
            [
                str(a.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                str(a.sign_in_time),
                str(a.sign_out_time) if a.sign_out_time else "Active",
                a.visit_type or "",
            ]
            for a, u in att_rows_raw
        ]

        # Safety training records with linked user name
        training_rows_raw = session.exec(
            select(SafetyTraining, User)
            .join(User, SafetyTraining.user_account_number == User.account_number)
            .order_by(User.last_name)
        ).all()
        training_rows = [
            [
                str(t.id),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                "Yes" if t.orientation else "No",
                "Yes" if t.whmis else "No",
            ]
            for t, u in training_rows_raw
        ]

        # Community contacts (standalone, no user account linkage)
        contacts = session.exec(
            select(CommunityContact).order_by(CommunityContact.visited_at)
        ).all()
        contact_rows = [
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

        # Feedback submissions with admin responses
        feedback = session.exec(select(Feedback).order_by(Feedback.submitted_at)).all()
        feedback_rows = [
            [
                str(f.id),
                str(f.user_account_number),
                f"{f.first_name} {f.last_name}",
                str(f.submitted_at),
                "Yes" if f.urgent else "No",
                f.comment,
                f.admin_response or "",
            ]
            for f in feedback
        ]

    return [
        {
            "title": "Users",
            "headers": [
                "Account",
                "First Name",
                "Last Name",
                "Email",
                "Role",
                "Active",
                "Date of Birth",
                "Phone",
                "Address",
                "City",
                "Province",
                "Postal Code",
                "Emergency First Name",
                "Emergency Last Name",
                "Emergency Phone",
                "Allergies",
                "Health Concerns",
                "Policies Agreed",
                "Code of Conduct Agreed",
                "ID Checked",
                "Joined Date",
                "Interests",
                "Skills Training",
                "Safety Accreditations",
                "Warnings",
                "Banned",
                "Account Comments",
            ],
            "rows": user_rows,
        },
        {
            "title": "Active Memberships",
            "headers": [
                "ID",
                "Account",
                "Name",
                "Start Date",
                "End Date",
                "Description",
            ],
            "rows": mem_rows,
        },
        {
            "title": "Membership Dues",
            "headers": [
                "ID",
                "Account",
                "Name",
                "Month",
                "Amount Paid",
                "Payment Date",
            ],
            "rows": dues_rows,
        },
        {
            "title": "Consumable Transactions",
            "headers": [
                "ID",
                "Account",
                "Name",
                "Type",
                "Amount",
                "Date",
                "Description",
            ],
            "rows": cons_rows,
        },
        {
            "title": "Day Passes",
            "headers": ["ID", "Account", "Name", "Date", "Description"],
            "rows": dp_rows,
        },
        {
            "title": "Space Attendance",
            "headers": ["ID", "Account", "Name", "Sign In", "Sign Out", "Visit Type"],
            "rows": att_rows,
        },
        {
            "title": "Safety Training",
            "headers": ["ID", "Account", "Name", "Orientation", "WHMIS"],
            "rows": training_rows,
        },
        {
            "title": "Community Contacts",
            "headers": [
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
            ],
            "rows": contact_rows,
        },
        {
            "title": "Feedback",
            "headers": [
                "ID",
                "Account",
                "Name",
                "Submitted At",
                "Urgent",
                "Comment",
                "Admin Response",
            ],
            "rows": feedback_rows,
        },
    ]


# --- Daily Email Report ---


def build_daily_report_data() -> dict:
    """
    Assembles the data needed for the daily membership summary email.
    Returns a plain dict so email_service remains decoupled from the DB layer.

    Keys returned:
      hackspace_name             - display name of the space
      report_date                - formatted date string for the report header
      total_active_members       - current snapshot count of approved MEMBER accounts
      pending_approvals          - current count of accounts awaiting approval
      days                       - list of 7 dicts, one per day (oldest first),
                                   each holding per-day counts for every metric
      community_contacts_detail  - full detail for every community contact entry
                                   logged in the past 7 days, ordered by visit time
    """
    now = datetime.now()
    today = now.date()

    # Build the ordered list of the 7 dates: [today-6, today-5, ..., today]
    day_dates = [today - timedelta(days=i) for i in range(6, -1, -1)]

    # Window start: beginning of the oldest day in the range
    window_start = datetime.combine(day_dates[0], datetime.min.time())

    with Session(engine) as session:
        # Current snapshot totals — not per-day metrics
        active_count = (
            session.exec(
                select(func.count(User.account_number)).where(
                    or_(User.role == UserRole.MEMBER, User.role == "member"),
                    User.is_active.is_(True),
                )
            ).one()
            or 0
        )

        pending_count = (
            session.exec(
                select(func.count(User.account_number)).where(User.is_active.is_(False))
            ).one()
            or 0
        )

        # Fetch all records in the 7-day window once, then bucket by date in Python
        # to avoid issuing 7 separate queries per metric.

        new_members_raw = session.exec(
            select(User).where(User.joined_date >= window_start)
        ).all()

        sign_ins_raw = session.exec(
            select(SpaceAttendance).where(SpaceAttendance.sign_in_time >= window_start)
        ).all()

        day_passes_raw = session.exec(
            select(UserCredits)
            .where(UserCredits.credit_debit == "daypass")
            .where(UserCredits.date >= window_start)
        ).all()

        transactions_raw = session.exec(
            select(UserCredits)
            .where(
                or_(
                    UserCredits.credit_debit == "credit",
                    UserCredits.credit_debit == "debit",
                )
            )
            .where(UserCredits.date >= window_start)
        ).all()

        # Memberships whose end_date falls on one of the 7 days in the window
        expiring_raw = session.exec(
            select(ActiveMembership).where(
                func.date(ActiveMembership.end_date) >= str(day_dates[0]),
                func.date(ActiveMembership.end_date) <= str(today),
            )
        ).all()

        contacts_raw = session.exec(
            select(CommunityContact)
            .where(CommunityContact.visited_at >= window_start)
            .order_by(CommunityContact.visited_at)
        ).all()

        square_txns_raw = session.exec(
            select(SquareTransaction)
            .where(SquareTransaction.created_at >= window_start)
            .order_by(desc(SquareTransaction.created_at))
        ).all()

    # --- Bucket records by calendar date ---
    nm_by_day: dict = defaultdict(int)
    for u in new_members_raw:
        if u.joined_date:
            nm_by_day[u.joined_date.date()] += 1

    si_by_day: dict = defaultdict(int)
    vol_by_day: dict = defaultdict(int)
    for a in sign_ins_raw:
        si_by_day[a.sign_in_time.date()] += 1
        if a.visit_type in ("Volunteer", "Volunteer and Visit"):
            vol_by_day[a.sign_in_time.date()] += 1

    dp_by_day: dict = defaultdict(int)
    for c in day_passes_raw:
        dp_by_day[c.date.date()] += 1

    tx_by_day: dict = defaultdict(int)
    for c in transactions_raw:
        tx_by_day[c.date.date()] += 1

    ex_by_day: dict = defaultdict(int)
    for m in expiring_raw:
        ex_by_day[m.end_date.date()] += 1

    cc_by_day: dict = defaultdict(int)
    for c in contacts_raw:
        cc_by_day[c.visited_at.date()] += 1

    # --- Build the per-day list ---
    days = [
        {
            "date_label": d.strftime("%a %b %d"),
            "new_members": nm_by_day[d],
            "memberships_expiring": ex_by_day[d],
            "sign_ins": si_by_day[d],
            "volunteers": vol_by_day[d],
            "day_passes": dp_by_day[d],
            "transactions": tx_by_day[d],
            "community_contacts": cc_by_day[d],
        }
        for d in day_dates
    ]

    # --- Full community contact detail for the period ---
    community_contacts_detail = [
        {
            "name": f"{c.first_name} {c.last_name or ''}".strip(),
            "email": c.email,
            "phone": c.phone or "",
            "brought_in_by": c.brought_in_by or "",
            "visited_at": c.visited_at.strftime("%Y-%m-%d %H:%M"),
            "community_tour": "Yes" if c.is_community_tour else "No",
            "staff": c.staff_name or "",
            "notes": c.other_reason or "",
        }
        for c in contacts_raw
    ]

    # --- Recent Square/POS transactions for the period (newest first) ---
    recent_transactions_detail = [
        {
            "date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name": t.customer_name or "",
            "amount": f"${t.amount:.2f}",
            "description": t.description or "",
            "status": t.square_status.replace("_", " ").title(),
            "via": (
                "Cash (Square)"
                if t.square_status == "cash_square"
                else "Cash"
                if t.square_status == "cash"
                else "Local"
                if t.is_local
                else "Square"
            ),
        }
        for t in square_txns_raw
    ]

    return {
        "hackspace_name": get_setting("hackspace_name", "Hackspace"),
        "report_date": today.strftime("%B %d, %Y"),
        "total_active_members": int(active_count),
        "pending_approvals": int(pending_count),
        "days": days,
        "community_contacts_detail": community_contacts_detail,
        "recent_transactions_detail": recent_transactions_detail,
    }
