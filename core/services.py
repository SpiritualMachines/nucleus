from datetime import datetime, timedelta
from random import randint
from typing import List, Optional, Union

from sqlalchemy import or_, text
from sqlmodel import Session, desc, func, select

from core.database import engine
from core.models import (
    ActiveMembership,
    AppSetting,
    CommunityContact,
    Feedback,
    MembershipDues,
    SafetyTraining,
    SpaceAttendance,
    User,
    UserCredits,
    UserPreference,
    UserRole,
)
from core.security import get_password_hash, verify_password


# --- Application Settings ---


def get_setting(key: str, default: str = "") -> str:
    """Returns the value for a settings key, or default if not found."""
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return s.value if s else default


def set_setting(key: str, value: str):
    """Creates or updates a settings key."""
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        if s:
            s.value = value
        else:
            s = AppSetting(key=key, value=value)
        session.add(s)
        session.commit()


def set_sensitive_setting(key: str, value: str) -> None:
    """
    Stores a setting value and flags it as sensitive so the UI knows never to
    display it after saving. The value is stored in plaintext — the sensitivity
    flag is purely a UI-layer contract, not an encryption guarantee.
    Appropriate for API keys on a local SQLite deployment.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        if s:
            s.value = value
            s.is_sensitive = True
        else:
            s = AppSetting(key=key, value=value, is_sensitive=True)
        session.add(s)
        session.commit()


def sensitive_setting_is_configured(key: str) -> bool:
    """
    Returns True when a non-empty value has already been stored for a sensitive
    key. The UI uses this to decide whether to show an input field or the
    "configured / hidden" placeholder — it never needs the raw value.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return bool(s and s.value)


def get_sensitive_setting_value(key: str) -> str:
    """
    Returns the raw value stored for a sensitive setting key.
    This function is intended for internal service and email use only.
    It must never be called from a screen or any UI layer.
    """
    with Session(engine) as session:
        s = session.get(AppSetting, key)
        return s.value if s else ""


def initialize_default_settings(seed_values: dict = None):
    """
    Seeds the AppSetting table with default values on first run.
    Existing keys are never overwritten.
    seed_values allows the caller to pass file-based values as initial defaults.
    """
    defaults = {
        "hackspace_name": "Hackspace",
        "tag_name": "Makerspace",
        "app_name": "Nucleus Daemon",
        "app_version": "v0.9.71",
        "ascii_logo": "",
        "logout_timeout_minutes": "10",
        # Space operations
        "membership_grace_period_days": "0",
        "day_pass_cost_credits": "0",
        "max_concurrent_signins": "0",
        "backup_retention_days": "30",
        # Reporting and branding
        "app_currency_name": "Credits",
        "default_export_format": "csv",
        "report_header_text": "",
        "staff_email": "",
        # Security
        "min_password_length": "8",
        "sql_console_enabled": "true",
        "login_attempt_limit": "0",
        # Email reporting — resend_api_key is seeded separately via set_sensitive_setting
        "report_from_email": "onboarding@resend.dev",
        "report_to_email": "",
        "email_reports_enabled": "false",
        # 24-hour HH:MM time at which the daily report email is dispatched
        "report_send_time": "07:00",
    }
    if seed_values:
        defaults.update(seed_values)

    with Session(engine) as session:
        for key, value in defaults.items():
            if not session.get(AppSetting, key):
                session.add(AppSetting(key=key, value=value))
        session.commit()


# --- User Preferences ---


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


# --- Helper to generate ID ---
def generate_account_number(session: Session) -> int:
    """
    Generates a unique account number with the format:
    [9 Random Digits] + [Source: 1] + [Month: MM] + [Year: YY]
    Total Length: 14 Digits.
    """
    now = datetime.now()
    month_str = now.strftime("%m")  # 2 digit month
    year_str = now.strftime("%y")  # 2 digit year
    source_id = "1"  # Source ID for this app

    while True:
        # Generate random 9 digit int
        random_part = randint(100000000, 999999999)

        # Construct: RRRRRRRRR + 1 + MM + YY
        candidate_str = f"{random_part}{source_id}{month_str}{year_str}"
        acc_num = int(candidate_str)

        # Verify uniqueness
        existing = session.get(User, acc_num)
        if not existing:
            return acc_num


# --- Membership Logic ---


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


# --- User Management ---


def get_users(roles: List[Union[UserRole, str]] = None) -> List[User]:
    """
    Fetches users, optionally filtered by a list of roles.
    Accepts both UserRole Enums and raw strings.
    """
    with Session(engine) as session:
        if roles:
            # Robust filtering: generate variations to catch case mismatches
            safe_roles = []
            for r in roles:
                val = r.value if hasattr(r, "value") else str(r)
                # Add lowercase, uppercase, and title case to be absolutely sure
                safe_roles.append(val.lower())
                safe_roles.append(val.upper())
                safe_roles.append(val.title())
                safe_roles.append(val)  # Add exact value just in case

            # Remove duplicates
            safe_roles = list(set(safe_roles))

            # Use the IN clause with the safe string list
            statement = select(User).where(User.role.in_(safe_roles))
        else:
            statement = select(User)

        return session.exec(statement).all()


def get_pending_users() -> List[User]:
    with Session(engine) as session:
        statement = select(User).where(User.is_active.is_(False))
        return session.exec(statement).all()


def search_users(query_str: str) -> List[User]:
    with Session(engine) as session:
        query_str = f"%{query_str}%"
        statement = select(User).where(
            or_(
                User.first_name.ilike(query_str),
                User.last_name.ilike(query_str),
                User.email.ilike(query_str),
            )
        )
        return session.exec(statement).all()


def get_user_by_account(acct_num: int) -> Optional[User]:
    with Session(engine) as session:
        return session.get(User, acct_num)


def approve_user(admin_acct: int, target_acct: int):
    with Session(engine) as session:
        # Verify admin
        admin = session.get(User, admin_acct)
        # Check against both string and enum for robustness
        role_str = (
            str(admin.role).lower()
            if isinstance(admin.role, str)
            else admin.role.value.lower()
        )

        if role_str not in ["admin", "staff"]:
            raise PermissionError("Only Staff/Admin can approve users.")

        target = session.get(User, target_acct)
        if target:
            target.is_active = True
            # Defaults to Community on approval unless manually changed
            target_role_str = (
                str(target.role).lower()
                if isinstance(target.role, str)
                else target.role.value.lower()
            )

            if target_role_str != "member":
                target.role = UserRole.COMMUNITY

            session.add(target)
            session.commit()


def register_user(user_data: dict, password: str) -> User:
    """
    Standard registration (pending approval). Enforces the min_password_length
    setting before creating the account.
    """
    min_len = int(get_setting("min_password_length", "8"))
    if len(password) < min_len:
        raise ValueError(f"Password must be at least {min_len} characters.")

    with Session(engine) as session:
        # Check email unique
        existing = session.exec(
            select(User).where(User.email == user_data["email"])
        ).first()
        if existing:
            raise ValueError("Email already registered.")

        # Create User
        acct_num = generate_account_number(session)
        # Default new users to COMMUNITY role (string)
        new_user = User(
            account_number=acct_num,
            password_hash=get_password_hash(password),
            role=UserRole.COMMUNITY,
            is_active=False,  # Pending approval
            **user_data,
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user


def register_verified_user(user_data: dict, password: str) -> User:
    """
    Staff-assisted registration (Active immediately, ID checked). Enforces the
    min_password_length setting before creating the account.
    """
    min_len = int(get_setting("min_password_length", "8"))
    if len(password) < min_len:
        raise ValueError(f"Password must be at least {min_len} characters.")

    with Session(engine) as session:
        # Check email unique
        existing = session.exec(
            select(User).where(User.email == user_data["email"])
        ).first()
        if existing:
            raise ValueError("Email already registered.")

        # Create User
        acct_num = generate_account_number(session)

        # Remove conflicting keys from user_data if present
        # This prevents "got multiple values for keyword argument" error
        user_data.pop("role", None)
        user_data.pop("is_active", None)
        user_data.pop("id_checked", None)

        # Override fields for verified status
        new_user = User(
            account_number=acct_num,
            password_hash=get_password_hash(password),
            role=UserRole.COMMUNITY,
            is_active=True,  # Active immediately
            id_checked=True,  # Verified in person
            **user_data,
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user


def update_user_details(acct_num: int, data: dict) -> User:
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            raise ValueError("User not found")

        for key, value in data.items():
            setattr(user, key, value)

        session.add(user)
        session.commit()
        session.refresh(user)
        return user


# --- Authentication ---


def authenticate_user(email: str, password: str) -> Optional[User]:
    """
    Authenticates by email and password. Enforces login_attempt_limit if set
    (0 = unlimited). Failed attempt counts are stored as UserPreference entries so
    no schema change is required on the User table. On successful login the attempt
    counter is reset. Raises ValueError with a lockout message when the account is
    locked; returns None on invalid credentials without revealing which field failed.
    """
    limit = int(get_setting("login_attempt_limit", "0"))

    with Session(engine) as session:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        if not user:
            return None

        acct = user.account_number

        # Check whether the account is currently locked
        if limit > 0:
            locked_until_str = session.exec(
                select(UserPreference)
                .where(UserPreference.user_account_number == acct)
                .where(UserPreference.key == "login_locked_until")
            ).first()
            if locked_until_str and locked_until_str.value:
                try:
                    locked_until = datetime.fromisoformat(locked_until_str.value)
                    if datetime.now() < locked_until:
                        raise ValueError(
                            "Account locked due to too many failed attempts. "
                            "Please contact staff."
                        )
                    else:
                        # Lock window has expired — clear it
                        locked_until_str.value = ""
                        session.add(locked_until_str)
                        session.commit()
                except ValueError as exc:
                    # Re-raise lockout messages; swallow datetime parse errors
                    if "Account locked" in str(exc):
                        raise

        if not verify_password(password, user.password_hash):
            # Increment failure counter when a limit is configured
            if limit > 0:
                attempts_row = session.exec(
                    select(UserPreference)
                    .where(UserPreference.user_account_number == acct)
                    .where(UserPreference.key == "failed_login_attempts")
                ).first()
                attempts = int(attempts_row.value) + 1 if attempts_row else 1

                if attempts_row:
                    attempts_row.value = str(attempts)
                    session.add(attempts_row)
                else:
                    session.add(
                        UserPreference(
                            user_account_number=acct,
                            key="failed_login_attempts",
                            value=str(attempts),
                        )
                    )

                if attempts >= limit:
                    # Lock the account for 30 minutes
                    lock_expiry = (datetime.now() + timedelta(minutes=30)).isoformat()
                    lock_row = session.exec(
                        select(UserPreference)
                        .where(UserPreference.user_account_number == acct)
                        .where(UserPreference.key == "login_locked_until")
                    ).first()
                    if lock_row:
                        lock_row.value = lock_expiry
                        session.add(lock_row)
                    else:
                        session.add(
                            UserPreference(
                                user_account_number=acct,
                                key="login_locked_until",
                                value=lock_expiry,
                            )
                        )

                session.commit()
            return None

        # Successful login — clear failure tracking
        if limit > 0:
            for key in ("failed_login_attempts", "login_locked_until"):
                row = session.exec(
                    select(UserPreference)
                    .where(UserPreference.user_account_number == acct)
                    .where(UserPreference.key == key)
                ).first()
                if row:
                    row.value = ""
                    session.add(row)
            session.commit()

        return user


# --- Password Management ---


def update_user_password(acct_num: int, old_password: str, new_password: str):
    """
    Verifies the user's current password first, then enforces the min_password_length
    setting, and finally replaces the hash. Old password is checked before new password
    policy so the caller cannot use policy errors to probe whether the current password
    is correct.
    """
    with Session(engine) as session:
        user = session.get(User, acct_num)
        if not user:
            raise ValueError("User not found.")
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Current password is incorrect.")

        min_len = int(get_setting("min_password_length", "8"))
        if len(new_password) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters.")

        user.password_hash = get_password_hash(new_password)
        session.add(user)
        session.commit()


# --- Attendance ---


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


# --- Memberships & Day Passes ---


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


def get_user_day_passes(acct_num: int):
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


# --- Consumables / Transactions ---


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


# --- Feedback ---


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


# --- Community Contacts ---


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


# --- Admin SQL ---


def execute_raw_sql(query: str) -> dict:
    """
    Executes raw SQL query.
    Returns a dict with success status, headers/rows (for SELECT), or rowcount (for INSERT/UPDATE).
    """
    with Session(engine) as session:
        try:
            # Execute raw query
            result = session.execute(text(query))
            session.commit()

            # Check if it's a SELECT statement (returns rows)
            if result.returns_rows:
                headers = list(result.keys())
                # Convert all values to string for display safety
                rows = [list(map(str, row)) for row in result.all()]
                return {
                    "success": True,
                    "type": "select",
                    "headers": headers,
                    "rows": rows,
                }
            else:
                # INSERT / UPDATE / DELETE
                return {
                    "success": True,
                    "type": "modification",
                    "rows_affected": result.rowcount,
                }

        except Exception as e:
            return {"success": False, "error": str(e)}


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


# --- Period Traction Report ---


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
    from collections import defaultdict

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

    # --- Bucket records by calendar date ---
    nm_by_day: dict = defaultdict(int)
    for u in new_members_raw:
        if u.joined_date:
            nm_by_day[u.joined_date.date()] += 1

    si_by_day: dict = defaultdict(int)
    for a in sign_ins_raw:
        si_by_day[a.sign_in_time.date()] += 1

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

    return {
        "hackspace_name": get_setting("hackspace_name", "Hackspace"),
        "report_date": today.strftime("%B %d, %Y"),
        "total_active_members": int(active_count),
        "pending_approvals": int(pending_count),
        "days": days,
        "community_contacts_detail": community_contacts_detail,
    }
