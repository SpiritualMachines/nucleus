"""Dashboard modals package.

Shared helpers are defined here and imported by sub-modules.
All modal classes are re-exported for convenient access.
"""


# --- Helper to safely get role name (Fixes AttributeError) ---
def get_safe_role_name(role_obj):
    """Safely extracts the name from a UserRole, handling cases where it's a raw string."""
    if hasattr(role_obj, "name"):
        return role_obj.name
    return str(role_obj).upper()


# Recognised visit types shown to the user at sign-in
VISIT_TYPES = [
    "Makerspace",
    "Workshop",
    "Digital Creator",
    "Digital Creator Camp",
    "Volunteer",
    "Volunteer and Visit",
]

# Actions available in the Member Action modal, ordered by index for dispatch
MEMBER_ACTIONS = [
    "Edit User Profile / Role",
    "Add Membership",
    "Edit Membership",
    "Transaction (Credit/Debit)",
    "Add Day Pass",
    "View Day Pass History",
    "Edit Sign Ins",
    "Activate Square Subscription",
]

# Re-export all modal classes from sub-modules
from screens.modals.day_pass import AddDayPassModal, DayPassHistoryModal  # noqa: E402
from screens.modals.feedback import FeedbackViewModal  # noqa: E402
from screens.modals.member_actions import (  # noqa: E402
    ManageSignInsModal,
    MemberActionModal,
    StaffEditUserScreen,
)
from screens.modals.membership import AddMembershipModal, ManageMembershipsModal  # noqa: E402
from screens.modals.reports import (  # noqa: E402
    CommunityContactsReportModal,
    PeriodTractionReportModal,
)
from screens.modals.signin import (  # noqa: E402
    ConfirmSignOutScreen,
    PostActionCountdownModal,
    SelectVisitTypeModal,
)
from screens.modals.storage import (  # noqa: E402
    StorageAssignModal,
    StorageEditModal,
    StorageViewModal,
)
from screens.modals.subscriptions import ActivateSubscriptionModal  # noqa: E402
from screens.modals.transactions import TransactionModal, ViewCreditsModal  # noqa: E402

__all__ = [
    # Shared helpers
    "get_safe_role_name",
    "VISIT_TYPES",
    "MEMBER_ACTIONS",
    # signin
    "SelectVisitTypeModal",
    "ConfirmSignOutScreen",
    "PostActionCountdownModal",
    # member_actions
    "MemberActionModal",
    "StaffEditUserScreen",
    "ManageSignInsModal",
    # transactions
    "TransactionModal",
    "ViewCreditsModal",
    # membership
    "AddMembershipModal",
    "ManageMembershipsModal",
    # day_pass
    "AddDayPassModal",
    "DayPassHistoryModal",
    # feedback
    "FeedbackViewModal",
    # reports
    "CommunityContactsReportModal",
    "PeriodTractionReportModal",
    # subscriptions
    "ActivateSubscriptionModal",
    # storage
    "StorageAssignModal",
    "StorageViewModal",
    "StorageEditModal",
]
