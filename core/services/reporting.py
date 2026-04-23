"""Reporting functions for period traction, people export, and daily email."""

import calendar
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlmodel import Session, desc, func, select

from core.database import engine
from core.models import (
    ActiveMembership,
    CommunityContact,
    DayPass,
    Feedback,
    MembershipDues,
    ProductSale,
    ProductTier,
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
    "get_products_services_report_data",
    "get_everything_people_data",
    "build_daily_report_data",
    "build_monthly_transaction_report_data",
    "build_period_transaction_report_data",
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
            select(DayPass, User)
            .join(User, DayPass.user_account_number == User.account_number)
            .where(
                DayPass.date >= start_date,
                DayPass.date <= end_date,
            )
            .order_by(DayPass.date)
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

        # Product sales recorded via the POS cart or the Edit Allocation modal
        sale_rows = session.exec(
            select(ProductSale)
            .where(
                ProductSale.sold_at >= start_date,
                ProductSale.sold_at <= end_date,
            )
            .order_by(ProductSale.sold_at)
        ).all()
        product_sales = [
            [
                str(ps.id),
                ps.sold_at.strftime("%Y-%m-%d %H:%M"),
                str(ps.transaction_id),
                ps.item_name,
                str(
                    int(ps.quantity) if ps.quantity == int(ps.quantity) else ps.quantity
                ),
                f"${ps.unit_price:.2f}",
                f"${ps.unit_price * ps.quantity:.2f}",
            ]
            for ps in sale_rows
        ]

    return {
        "memberships": memberships,
        "day_passes": day_passes,
        "consumables": consumables,
        "sign_ins": sign_ins,
        "community_contacts": community_contacts,
        "product_sales": product_sales,
    }


def get_products_services_report_data(start_date: datetime, end_date: datetime) -> list:
    """Returns multi-section report data covering all products and services sold
    in the given date range.

    Sections returned:
      Transactions   — all completed/cash/local SquareTransaction records
      Product Sales  — inventory items sold via POS or Edit Allocation
      Day Passes     — day pass activations during the period
      Memberships    — membership periods that started during the period

    Each section is a dict with 'title', 'headers', 'rows' compatible with
    the multi-section CSV and PDF exporters.
    """
    completed_statuses = ("completed", "cash", "cash_square", "local")

    with Session(engine) as session:
        txn_rows_raw = session.exec(
            select(SquareTransaction)
            .where(
                SquareTransaction.created_at >= start_date,
                SquareTransaction.created_at <= end_date,
                SquareTransaction.square_status.in_(completed_statuses),
            )
            .order_by(SquareTransaction.created_at)
        ).all()
        txn_rows = [
            [
                str(t.id),
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.customer_name or "",
                f"${t.amount:.2f}",
                t.description or "",
                t.square_status,
                t.processed_by or "",
            ]
            for t in txn_rows_raw
        ]

        sale_rows_raw = session.exec(
            select(ProductSale)
            .where(
                ProductSale.sold_at >= start_date,
                ProductSale.sold_at <= end_date,
            )
            .order_by(ProductSale.sold_at)
        ).all()
        product_rows = [
            [
                str(ps.id),
                ps.sold_at.strftime("%Y-%m-%d %H:%M"),
                str(ps.transaction_id),
                ps.item_name,
                str(
                    int(ps.quantity) if ps.quantity == int(ps.quantity) else ps.quantity
                ),
                f"${ps.unit_price:.2f}",
                f"${ps.unit_price * ps.quantity:.2f}",
            ]
            for ps in sale_rows_raw
        ]

        dp_pairs = session.exec(
            select(DayPass, User)
            .join(User, DayPass.user_account_number == User.account_number)
            .where(
                DayPass.date >= start_date,
                DayPass.date <= end_date,
            )
            .order_by(DayPass.date)
        ).all()
        daypass_rows = [
            [
                str(dp.id),
                dp.date.strftime("%Y-%m-%d"),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                dp.description or "",
            ]
            for dp, u in dp_pairs
        ]

        mem_pairs = session.exec(
            select(ActiveMembership, User)
            .join(User, ActiveMembership.user_account_number == User.account_number)
            .where(
                ActiveMembership.start_date >= start_date,
                ActiveMembership.start_date <= end_date,
            )
            .order_by(ActiveMembership.start_date)
        ).all()
        membership_rows = [
            [
                str(m.id),
                m.start_date.strftime("%Y-%m-%d"),
                m.end_date.strftime("%Y-%m-%d"),
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                m.description or "",
            ]
            for m, u in mem_pairs
        ]

    return [
        {
            "title": "Transactions",
            "headers": [
                "ID",
                "Date",
                "Customer",
                "Amount",
                "Description",
                "Status",
                "Processed By",
            ],
            "rows": txn_rows,
        },
        {
            "title": "Product Sales",
            "headers": [
                "Sale ID",
                "Date",
                "Transaction ID",
                "Item",
                "Qty",
                "Unit Price",
                "Total",
            ],
            "rows": product_rows,
        },
        {
            "title": "Day Passes",
            "headers": ["ID", "Date", "Account", "Name", "Description"],
            "rows": daypass_rows,
        },
        {
            "title": "Memberships",
            "headers": [
                "ID",
                "Start Date",
                "End Date",
                "Account",
                "Name",
                "Description",
            ],
            "rows": membership_rows,
        },
    ]


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
            select(DayPass, User)
            .join(User, DayPass.user_account_number == User.account_number)
            .order_by(User.last_name, DayPass.date)
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

        # All Square/POS financial transactions ordered by date
        txn_rows_raw = session.exec(
            select(SquareTransaction).order_by(SquareTransaction.created_at)
        ).all()
        txn_rows = [
            [
                str(t.id),
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.customer_name or "",
                t.customer_email or "",
                t.customer_phone or "",
                f"${t.amount:.2f}",
                t.description or "",
                t.square_status or "",
                "Yes" if t.is_local else "No",
                t.processed_by or "",
                t.refund_status or "",
            ]
            for t in txn_rows_raw
        ]

        # Product sales recorded via POS cart or Edit Allocation
        sale_rows_raw = session.exec(
            select(ProductSale).order_by(ProductSale.sold_at)
        ).all()
        sale_rows = [
            [
                str(ps.id),
                ps.sold_at.strftime("%Y-%m-%d %H:%M"),
                str(ps.transaction_id),
                ps.item_name,
                str(
                    int(ps.quantity) if ps.quantity == int(ps.quantity) else ps.quantity
                ),
                f"${ps.unit_price:.2f}",
                f"${ps.unit_price * ps.quantity:.2f}",
            ]
            for ps in sale_rows_raw
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
        {
            "title": "Transactions",
            "headers": [
                "ID",
                "Date",
                "Customer Name",
                "Email",
                "Phone",
                "Amount",
                "Description",
                "Status",
                "Local",
                "Processed By",
                "Refund Status",
            ],
            "rows": txn_rows,
        },
        {
            "title": "Product Sales",
            "headers": [
                "Sale ID",
                "Date",
                "Transaction ID",
                "Item",
                "Qty",
                "Unit Price",
                "Total",
            ],
            "rows": sale_rows,
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
            select(DayPass).where(DayPass.date >= window_start)
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

        # Collect names of all membership tiers priced at $0 so we can identify
        # free promotional memberships by matching the description field on activation.
        free_tier_names = {
            t.name
            for t in session.exec(
                select(ProductTier).where(
                    ProductTier.tier_type == "membership",
                    ProductTier.price == 0.0,
                )
            ).all()
        }

        # Memberships started in the window whose description matches a free tier.
        free_memberships_raw = (
            session.exec(
                select(ActiveMembership).where(
                    ActiveMembership.start_date >= window_start,
                    ActiveMembership.description.in_(free_tier_names),
                )
            ).all()
            if free_tier_names
            else []
        )

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

    fm_by_day: dict = defaultdict(int)
    for m in free_memberships_raw:
        fm_by_day[m.start_date.date()] += 1

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
            "free_memberships": fm_by_day[d],
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

    # Split transactions into past 24 hours and past 7 days for separate tables.
    cutoff_24h = now - timedelta(hours=24)

    def _format_txn(t):
        return {
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

    transactions_24h = [
        _format_txn(t) for t in square_txns_raw if t.created_at >= cutoff_24h
    ]
    transactions_7d = [_format_txn(t) for t in square_txns_raw]

    return {
        "hackspace_name": get_setting("hackspace_name", "Hackspace"),
        "report_date": today.strftime("%B %d, %Y"),
        "total_active_members": int(active_count),
        "pending_approvals": int(pending_count),
        "days": days,
        "community_contacts_detail": community_contacts_detail,
        "transactions_24h": transactions_24h,
        "transactions_7d": transactions_7d,
    }


def build_monthly_transaction_report_data(year: int, month: int) -> dict:
    """
    Assembles all transaction data for the given calendar month, split into
    card (Square Terminal completions) and cash/local categories.

    Returns a plain dict so email_service remains decoupled from the ORM layer.

    Keys returned:
      hackspace_name      - display name of the space
      month_label         - human-readable label, e.g. "March 2026"
      year                - int
      month               - int (1-12)
      card_transactions   - list of dicts for square_status == "completed"
      cash_transactions   - list of dicts for square_status in
                            ("cash", "cash_square", "local")
      card_total          - float sum of all card transaction amounts
      cash_total          - float sum of all cash transaction amounts
    """
    first_day = datetime(year, month, 1, 0, 0, 0)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num, 23, 59, 59)

    card_statuses = ("completed",)
    cash_statuses = ("cash", "cash_square", "local")

    with Session(engine) as session:
        all_txns = session.exec(
            select(SquareTransaction)
            .where(
                SquareTransaction.created_at >= first_day,
                SquareTransaction.created_at <= last_day,
                or_(
                    SquareTransaction.square_status.in_(card_statuses),
                    SquareTransaction.square_status.in_(cash_statuses),
                ),
            )
            .order_by(SquareTransaction.created_at)
        ).all()

    def _row(t):
        return {
            "id": t.id,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name": t.customer_name or "",
            "description": t.description or "",
            "amount": t.amount,
            "amount_fmt": f"${t.amount:.2f}",
            "processed_by": t.processed_by or "",
        }

    card_rows = [_row(t) for t in all_txns if t.square_status in card_statuses]
    cash_rows = [_row(t) for t in all_txns if t.square_status in cash_statuses]

    return {
        "hackspace_name": get_setting("hackspace_name", "Hackspace"),
        "month_label": datetime(year, month, 1).strftime("%B %Y"),
        "year": year,
        "month": month,
        "card_transactions": card_rows,
        "cash_transactions": cash_rows,
        "card_total": sum(r["amount"] for r in card_rows),
        "cash_total": sum(r["amount"] for r in cash_rows),
    }


def build_period_transaction_report_data(
    start_date: datetime, end_date: datetime
) -> dict:
    """
    Assembles transaction data for an arbitrary date range, split into card
    (Square Terminal completions) and cash/local categories. Mirrors the
    structure of build_monthly_transaction_report_data but accepts explicit
    start and end datetimes so it can be used for any user-selected period.

    Returns a plain dict so export and email layers remain decoupled from the ORM.

    Keys returned:
      hackspace_name      - display name of the space
      period_label        - human-readable range, e.g. "2026-01-01 to 2026-03-31"
      card_transactions   - list of dicts for square_status == "completed"
      cash_transactions   - list of dicts for square_status in
                            ("cash", "cash_square", "local")
      card_total          - float sum of all card transaction amounts
      cash_total          - float sum of all cash transaction amounts
    """
    card_statuses = ("completed",)
    cash_statuses = ("cash", "cash_square", "local")

    with Session(engine) as session:
        all_txns = session.exec(
            select(SquareTransaction)
            .where(
                SquareTransaction.created_at >= start_date,
                SquareTransaction.created_at <= end_date,
                or_(
                    SquareTransaction.square_status.in_(card_statuses),
                    SquareTransaction.square_status.in_(cash_statuses),
                ),
            )
            .order_by(SquareTransaction.created_at)
        ).all()

    def _row(t):
        return {
            "id": t.id,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name": t.customer_name or "",
            "description": t.description or "",
            "amount": t.amount,
            "amount_fmt": f"${t.amount:.2f}",
            "processed_by": t.processed_by or "",
        }

    card_rows = [_row(t) for t in all_txns if t.square_status in card_statuses]
    cash_rows = [_row(t) for t in all_txns if t.square_status in cash_statuses]

    period_label = (
        f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    return {
        "hackspace_name": get_setting("hackspace_name", "Hackspace"),
        "period_label": period_label,
        "card_transactions": card_rows,
        "cash_transactions": cash_rows,
        "card_total": sum(r["amount"] for r in card_rows),
        "cash_total": sum(r["amount"] for r in cash_rows),
    }
