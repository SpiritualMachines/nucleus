from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, String, Text
from sqlmodel import Field, Relationship, SQLModel


# --- Application Settings Table ---


class AppSetting(SQLModel, table=True):
    """
    Key-value store for admin-configurable application settings.
    Replaces the flat settings.txt file for runtime configuration.
    """

    key: str = Field(primary_key=True)
    value: str = Field(default="")


class UserPreference(SQLModel, table=True):
    """
    Per-user preference store. Each row holds one preference key for one account.
    Values are always stored as strings and cast at the call site, following the
    same pattern as AppSetting. Preferences are fetched by (user_account_number, key)
    rather than by primary key, so the synthetic integer id is used only for the
    table constraint.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number", index=True)
    key: str = Field(max_length=100)
    value: str = Field(default="")


# --- Enums for strict typing ---
class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    MEMBER = "member"
    COMMUNITY = "community"


# --- Detail Tables ---


class SpaceAttendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number")
    sign_in_time: datetime = Field(default_factory=datetime.now)
    sign_out_time: Optional[datetime] = Field(default=None)
    visit_type: Optional[str] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="attendance")


class MembershipDues(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number")
    month: str
    amount_paid: float = 0.0
    payment_date: datetime = Field(default_factory=datetime.now)
    user: Optional["User"] = Relationship(back_populates="dues")


class UserCredits(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number")
    credits: float = 0.0  # Changed to float for currency
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    credit_debit: str = "credit"  # 'credit' or 'debit'
    date: datetime = Field(default_factory=datetime.now)
    user: Optional["User"] = Relationship(back_populates="credits")


class SafetyTraining(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number")
    orientation: bool = False
    whmis: bool = False
    user: Optional["User"] = Relationship(back_populates="training")


class CommunityContact(SQLModel, table=True):
    """
    Lightweight contact record for walk-in visitors who are not registered members.
    Captures interest data and visit reason without requiring a full account.
    Staff community tour records set is_community_tour=True and require staff_name
    to identify who logged the visit.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str = Field(default="")
    last_name: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: str = Field(default="")
    brought_in_by: Optional[str] = Field(default=None)
    other_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    visited_at: datetime = Field(default_factory=datetime.now)
    is_community_tour: bool = Field(default=False)
    staff_name: Optional[str] = Field(default=None, sa_column=Column(Text))


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int
    first_name: str
    last_name: str
    submitted_at: datetime = Field(default_factory=datetime.now)
    urgent: bool = False
    comment: str = Field(sa_column=Column(Text))
    admin_response: Optional[str] = Field(default=None, sa_column=Column(Text))


class ActiveMembership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_number: int = Field(foreign_key="user.account_number")
    start_date: datetime
    end_date: datetime
    # ADDED: Description field
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    user: Optional["User"] = Relationship(back_populates="memberships")


# --- Main User Table ---


class User(SQLModel, table=True):
    account_number: int = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    # FIX: Explicitly use String column to avoid SQLAlchemy Enum name/value mismatch
    role: UserRole = Field(default=UserRole.COMMUNITY, sa_column=Column(String))
    is_active: bool = False  # False until approved by staff

    # Personal Info
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    phone: str = Field(max_length=50)
    date_of_birth: Optional[datetime] = None

    # Address
    street_address: str = Field(max_length=100)
    city: str = Field(max_length=50)
    province: str = Field(max_length=50)
    postal_code: str = Field(max_length=50)

    # Emergency Contact
    emergency_first_name: str = Field(max_length=50)
    emergency_last_name: str = Field(max_length=50)
    emergency_phone: str = Field(max_length=50)

    # Health & Safety Data
    allergies: Optional[str] = Field(default=None, max_length=100)
    health_concerns: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Agreements
    policies_agreed: bool = False
    code_of_conduct_agreed: bool = False
    id_checked: bool = False

    # Metadata
    # FIX: Make optional to handle legacy data without dates, or ensure backfill
    joined_date: Optional[datetime] = Field(default_factory=datetime.now)

    interests: Optional[str] = Field(default=None, sa_column=Column(Text))
    skills_training: Optional[str] = Field(default=None, sa_column=Column(Text))
    safety_accreditations: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Staff Managed
    warnings: Optional[str] = Field(default=None, sa_column=Column(Text))
    banned: bool = False
    account_comments: Optional[str] = Field(default=None, sa_column=Column(Text))

    # --- Relationships ---
    dues: List[MembershipDues] = Relationship(back_populates="user")
    attendance: List[SpaceAttendance] = Relationship(back_populates="user")
    credits: List[UserCredits] = Relationship(back_populates="user")
    training: List[SafetyTraining] = Relationship(back_populates="user")
    memberships: List[ActiveMembership] = Relationship(back_populates="user")
