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
    When is_sensitive is True, the UI must never display the stored value —
    it shows a "configured / hidden" placeholder instead and only allows
    the value to be replaced, never read back.
    """

    key: str = Field(primary_key=True)
    value: str = Field(default="")
    is_sensitive: bool = Field(default=False)


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

    # Demographic and outreach fields added for walk-in visitor research
    pronouns: Optional[str] = Field(default=None)
    age_range: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    how_heard: Optional[str] = Field(default=None)

    # Opt-in preferences — all default to False (no implicit consent)
    opt_in_updates: bool = Field(default=False)
    opt_in_volunteer: bool = Field(default=False)
    opt_in_teaching: bool = Field(default=False)


class SquareTransactionStatus(str, Enum):
    """
    Lifecycle states for a SquareTransaction record.
    LOCAL means the transaction was recorded without Square (terminal disabled).
    All other statuses reflect values returned by the Square Terminal API.
    """

    LOCAL = "local"
    CASH = "cash"
    CASH_SQUARE = "cash_square"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    ERROR = "error"


class SquareTransaction(SQLModel, table=True):
    """
    Audit record for every manual transaction processed through the Purchases tab.
    Records are created whether Square Terminal is active or not — when the terminal
    is disabled, is_local is True and all square_* fields remain null.
    The square_raw_response field stores the full JSON response from the Square API
    for audit and reconciliation purposes.
    Customer fields are entered by staff at the time of the transaction; the record
    is not required to be linked to a registered user account.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Customer info — may not correspond to a registered user account
    user_account_number: Optional[int] = Field(default=None, index=True)
    customer_name: str = Field(default="")
    customer_email: Optional[str] = Field(default=None)
    customer_phone: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Financial
    amount: float = Field(default=0.0)  # stored in dollars

    # Square Terminal API response fields — null when is_local=True
    square_checkout_id: Optional[str] = Field(default=None)
    square_payment_id: Optional[str] = Field(default=None)
    square_order_id: Optional[str] = Field(default=None)
    square_device_id: Optional[str] = Field(default=None)
    square_location_id: Optional[str] = Field(default=None)
    square_status: str = Field(default=SquareTransactionStatus.LOCAL)
    square_raw_response: Optional[str] = Field(default=None, sa_column=Column(Text))

    # True when Square was not used; False when a terminal checkout was attempted
    is_local: bool = Field(default=True)


class PosConfig(SQLModel, table=True):
    """
    Point of Sale configuration. Always contains exactly one row (id=1).
    Use get_pos_config() in square_service to retrieve or create it.
    The square_access_token field stores the Square API access token in plaintext —
    the same model used for the Resend API key in AppSetting. The token is never
    pre-populated or displayed in the UI after being saved.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    square_enabled: bool = Field(default=False)
    square_environment: str = Field(default="sandbox")  # "sandbox" or "production"
    square_location_id: str = Field(default="")
    square_device_id: str = Field(default="")
    square_currency: str = Field(default="CAD")
    # Per-environment tokens stored separately so switching environments never
    # clears a stored credential. Neither value is ever shown in the UI after saving.
    square_access_token_sandbox: str = Field(default="")
    square_access_token_production: str = Field(default="")


class ProductTier(SQLModel, table=True):
    """
    Reusable template for membership or day pass products.
    Admins define tiers (e.g. "Monthly - Standard", "Day Pass") so staff can
    apply a standard package to an account without re-entering price and duration
    each time. When consumables_credits is set, that amount is automatically
    credited to the member's consumables balance when the tier is activated.
    tier_type must be either "membership" or "daypass".
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    tier_type: str  # "membership" or "daypass"
    price: float = Field(default=0.0)
    duration_days: Optional[int] = Field(default=None)  # membership only
    consumables_credits: Optional[float] = Field(
        default=None
    )  # bonus credits on activation
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_active: bool = Field(default=True)


class InventoryItem(SQLModel, table=True):
    """
    Reusable product or service available for selection when building a POS
    transaction. Staff pick items from the inventory cart in the Purchases tab
    instead of typing amounts and descriptions manually each time.
    Deactivated items are hidden from the picker but preserved for audit history.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="")
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    price: float = Field(default=0.0)
    is_active: bool = Field(default=True)


class StorageUnit(SQLModel, table=True):
    """
    Represents a physical storage bin/locker/shelf at the space.
    Units are created by staff and persist until explicitly deleted. Deactivating
    a unit (is_active=False) hides it from the active list but preserves history.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    unit_number: str = Field(default="")  # Human-readable label, e.g. "A-01"
    description: str = Field(default="")  # e.g. "Storage Bin", "Locker 3"
    is_active: bool = Field(default=True)

    assignments: List["StorageAssignment"] = Relationship(back_populates="unit")


class StorageAssignment(SQLModel, table=True):
    """
    Links a member (or named non-member) to a storage unit for a period of time.
    Archiving an assignment sets archived_at; archived records remain in the
    database and are shown in a separate history table below the active list.
    charge_total is a computed value (charge_unit_count * charge_cost_per_unit)
    stored redundantly for display efficiency and historical accuracy.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    unit_id: int = Field(foreign_key="storageunit.id", index=True)
    assigned_at: datetime = Field(default_factory=datetime.now)
    archived_at: Optional[datetime] = Field(default=None)

    # Either a registered member account or a freeform name — both are optional
    user_account_number: Optional[int] = Field(default=None, index=True)
    assigned_to_name: Optional[str] = Field(default=None)  # Freeform name override

    item_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Charges — all null when charges_owed is False
    charges_owed: bool = Field(default=False)
    charge_type: Optional[str] = Field(
        default=None
    )  # e.g. "Filament", "Large Format Printer"
    charge_unit_count: Optional[float] = Field(default=None)
    charge_cost_per_unit: Optional[float] = Field(default=None)
    charge_total: Optional[float] = Field(default=None)  # Pre-computed total
    charge_notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    unit: Optional["StorageUnit"] = Relationship(back_populates="assignments")


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

    # Square Subscription — populated when a recurring membership is activated.
    # Nucleus never stores payment details; Square owns the billing flow entirely.
    square_customer_id: Optional[str] = Field(default=None)
    square_subscription_id: Optional[str] = Field(default=None)
    square_subscription_status: Optional[str] = Field(default=None)
    square_subscription_checked_at: Optional[datetime] = Field(default=None)

    # --- Relationships ---
    dues: List[MembershipDues] = Relationship(back_populates="user")
    attendance: List[SpaceAttendance] = Relationship(back_populates="user")
    credits: List[UserCredits] = Relationship(back_populates="user")
    training: List[SafetyTraining] = Relationship(back_populates="user")
    memberships: List[ActiveMembership] = Relationship(back_populates="user")
