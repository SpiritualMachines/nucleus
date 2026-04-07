import time
from functools import partial

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    TabbedContent,
    TabPane,
)

from core import exporters, models, services, square_service
from core.email_service import send_transaction_receipt
from core.config import settings
from core.security import verify_password
from screens.dashboard_modals import (
    ActivateSubscriptionModal,
    AddDayPassModal,
    AddMembershipModal,
    CommunityContactsReportModal,
    ConfirmSignOutScreen,
    DayPassHistoryModal,
    FeedbackViewModal,
    ManageMembershipsModal,
    MemberActionModal,
    PeriodTractionReportModal,
    PeriodTransactionReportModal,
    PostActionCountdownModal,
    SelectVisitTypeModal,
    StorageAssignModal,
    StorageEditModal,
    StorageViewModal,
    TransactionModal,
    ViewCreditsModal,
    RefundConfirmModal,
    VISIT_TYPES,
)
from screens.directory_select import DirectorySelectScreen
from screens.edit_profile import ChangePasswordScreen, EditProfileScreen
from screens.registration import RegisterScreen
from screens.settings_screen import SettingsScreen


class Dashboard(Screen):
    CSS_PATH = "../theme/dashboard.tcss"

    # SQL preset queries for the Database tab quick-load buttons
    _SQL_PRESETS = {
        "sql_q1": (
            "SELECT first_name, last_name, allergies, health_concerns"
            " FROM user WHERE allergies != '' OR health_concerns != ''"
        ),
        "sql_q2": (
            "SELECT first_name, last_name, emergency_first_name,"
            " emergency_phone FROM user"
        ),
        "sql_q3": (
            "SELECT u.first_name, u.last_name, u.email FROM user u"
            " JOIN safetytraining s ON u.account_number ="
            " s.user_account_number WHERE s.orientation = 0"
        ),
        "sql_q4": "SELECT role, COUNT(*) as count FROM user GROUP BY role",
        "sql_q5": (
            "SELECT u.first_name, u.last_name, s.sign_in_time,"
            " s.sign_out_time FROM spaceattendance s JOIN user u ON"
            " s.user_account_number = u.account_number WHERE"
            " s.sign_in_time BETWEEN '2025-01-01 00:00:00'"
            " AND '2025-12-31 23:59:59'"
        ),
    }

    # Table configuration for initialisation in on_mount. Each entry maps a
    # table widget ID to its column definitions and cursor type.  Columns
    # represented as (name, width) tuples use add_column with explicit widths;
    # plain string tuples use add_columns for simple cases.
    _TABLE_CONFIGS = [
        {
            "id": "feedback_table",
            "columns": [
                ("ID", 4),
                ("Date", 18),
                ("Name", 20),
                ("Urgent", 8),
                ("Comment Preview", 45),
                ("Response", 45),
            ],
            "cursor_type": "row",
        },
        {
            "id": "pending_table",
            "columns": ("Acct #", "Name", "Email", "Date Joined"),
            "cursor_type": "row",
        },
        {
            "id": "members_table",
            "columns": ("Acct #", "Name", "Role", "Email"),
            "cursor_type": "row",
        },
        {
            "id": "user_search_table",
            "columns": ("Acct #", "Name", "Email"),
            "cursor_type": "row",
        },
        {
            "id": "staff_user_search_table",
            "columns": ("Acct #", "Name", "Email"),
            "cursor_type": "row",
        },
        {
            "id": "pos_customer_search_table",
            "columns": ("Acct #", "Name", "Email", "Phone"),
            "cursor_type": "row",
        },
        {
            "id": "pos_txns_table",
            "columns": [
                ("ID", 5),
                ("Date", 18),
                ("Customer", 18),
                ("Amount", 10),
                ("Description", 24),
                ("Status", 12),
                ("Via", 8),
                ("Processed By", 16),
                ("Refunded By", 16),
                ("Refund Reason", 22),
            ],
            "cursor_type": "row",
        },
        {
            "id": "inv_available_table",
            "columns": [
                ("ID", 5),
                ("Name", 28),
                ("Description", 35),
                ("Price", 10),
            ],
            "cursor_type": "row",
        },
        {
            "id": "inv_cart_table",
            "columns": [
                ("Item", 28),
                ("Qty", 6),
                ("Unit Price", 12),
                ("Subtotal", 12),
            ],
            "cursor_type": "row",
        },
        {
            "id": "storage_active_table",
            "columns": [
                ("ID", 5),
                ("Unit", 10),
                ("Assigned To", 22),
                ("Item", 28),
                ("Notes", 22),
                ("Charge Type", 20),
                ("Total", 10),
                ("Assigned At", 18),
            ],
            "cursor_type": "row",
        },
        {
            "id": "storage_archived_table",
            "columns": [
                ("ID", 5),
                ("Unit", 10),
                ("Assigned To", 22),
                ("Item", 28),
                ("Charge Type", 20),
                ("Total", 10),
                ("Archived At", 18),
            ],
            "cursor_type": "row",
        },
    ]

    AUTO_LOGOUT_SECONDS = 600  # 10 Minutes

    # Track selected user for unified Existing User Transactions section
    selected_user_acct = None
    # Track selected POS transaction row for status checks
    selected_pos_txn_id = None
    # Track selected active assignment row in the Storage tab
    selected_storage_assignment_id = None
    # Inventory cart state -- reset per session in on_mount to avoid class-level sharing
    _cart: list = []
    _inv_selected_item: dict = None  # {id, name, price} from available table
    _inv_selected_cart_key: str = None  # row key of selected cart row
    _manual_entry_counter: int = 0  # increments to give each manual entry a unique key

    def compose(self) -> ComposeResult:
        user = self.app.current_user
        currency = services.get_setting("app_currency_name", "Credits")

        # --- DB COMPATIBILITY FIX ---
        # Ensure user.role is an Enum, not a raw string from SQLite
        # This prevents "AttributeError: 'str' object has no attribute 'value'"
        # and ensures permission checks (which compare Enums) work correctly.
        if isinstance(user.role, str):
            try:
                # 1. Try to convert by Value (e.g. "admin" -> UserRole.ADMIN)
                user.role = models.UserRole(user.role.lower())
            except ValueError:
                try:
                    # 2. Try to convert by Name (e.g. "ADMIN" -> UserRole.ADMIN)
                    user.role = models.UserRole[user.role.upper()]
                except KeyError:
                    # If all else fails, keep as string to prevent startup crash
                    pass
        # ----------------------------

        yield Header(show_clock=True)

        yield Label("", id="pending_alert", classes="hidden")

        with TabbedContent():
            with TabPane("My Profile"):
                yield from self._compose_profile_tab(user, currency)

            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                with TabPane("Staff Tools"):
                    yield from self._compose_staff_tools_tab(user)

            with TabPane("Purchases"):
                yield from self._compose_purchases_tab(user, currency)

            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                with TabPane("Reports"):
                    yield from self._compose_reports_tab()

            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                with TabPane("Storage"):
                    yield from self._compose_storage_tab()

            if user.role == models.UserRole.ADMIN:
                with TabPane("Database"):
                    yield from self._compose_database_tab()

            if user.role == models.UserRole.ADMIN:
                with TabPane("Settings", id="tab_settings"):
                    yield SettingsScreen()

            with TabPane("Feedback"):
                yield from self._compose_feedback_tab(user)

        # Security Timer Label -- docked above footer
        yield Label(f"Auto-logout: {self.AUTO_LOGOUT_SECONDS}s", id="logout_timer")
        yield Footer()

    def _compose_profile_tab(self, user, currency) -> ComposeResult:
        """Yields widgets for the My Profile tab."""
        # Safe role access (handles both Enum and String cases)
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        role_name = user.role.name if hasattr(user.role, "name") else str(user.role)

        yield Label(
            f"Welcome, {role_val.title()} {user.first_name}!",
            classes="title",
            id="welcome_lbl",
        )
        yield Label(f"Account Type: {role_name}", id="lbl_role")
        yield Label(f"Account #: {user.account_number}", id="lbl_acct")
        yield Label("Credit Balance: $0.00", id="lbl_balance")

        with Horizontal(classes="filter-row"):
            yield Button("Edit My Information", id="edit_profile_btn")
            yield Button("Change Password", id="change_pwd_btn")
        with Horizontal(classes="filter-row"):
            # Label updated on mount by update_signin_button
            yield Button("Sign In to Makerspace", id="signin_btn")
            yield Button("Logout", id="logout_btn")

        yield Label("My Preferences", classes="subtitle")

        yield Label("Preferred Visit Type (leave blank to always be asked):")
        yield Select(
            [("No preference (always ask)", "")] + [(vt, vt) for vt in VISIT_TYPES],
            id="pref_visit_type",
            value="",
        )

        yield Button("Save Preferences", id="btn_save_prefs")

    def _compose_staff_tools_tab(self, user) -> ComposeResult:
        """Yields widgets for the Staff Tools tab."""
        with Vertical(classes="management-section"):
            yield Label("User Management", classes="title")
            yield Button("Register New Member (In-Person)", id="btn_staff_reg")

        # Quick User Search
        with Vertical(classes="management-section"):
            yield Label("Quick User Search / Manage", classes="subtitle")
            yield Label("Search for a user to open their management menu:")

            with Horizontal(classes="search-row"):
                yield Input(
                    placeholder="Name or Email...",
                    id="staff_user_search_input",
                )
                yield Button("Search", id="btn_staff_user_search")

            yield DataTable(id="staff_user_search_table")

        with Vertical(classes="pending-section"):
            yield Label("Pending Approvals", classes="title")
            yield DataTable(id="pending_table")
            yield Label("Select a row, then click Approve.", classes="subtitle")

            # Stacked buttons
            with Vertical(classes="pending-buttons"):
                yield Button(
                    "Approve Selected Account",
                    variant="success",
                    id="approve_btn",
                )
                yield Button("Refresh List", id="refresh_pending")

    def _compose_purchases_tab(self, user, currency) -> ComposeResult:
        """Yields widgets for the Purchases tab."""
        with VerticalScroll():
            yield Label("Purchases", classes="title")

            # === STAFF / ADMIN VIEW ===
            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                # Subsection 0: Manual Transaction (Point of Sale)
                with Vertical(classes="purchase-section"):
                    pos_cfg = square_service.get_pos_config()
                    pos_btn_label = (
                        "Send to Square Terminal"
                        if pos_cfg.square_enabled
                        else "Record Transaction"
                    )
                    yield Label("Manual Transaction", classes="subtitle")

                    # Step 1: Inventory Cart
                    with Collapsible(title="Step 1: Select Items (Optional)", collapsed=True):
                        yield Label(
                            "Click an item row to select it, set the quantity,"
                            " then click Add to Cart."
                            " Amount and Description are auto-filled."
                        )
                        yield DataTable(id="inv_available_table")
                        with Horizontal(classes="filter-row"):
                            yield Label("Quantity:")
                            yield Input("1", id="inv_qty", type="number")
                            yield Button(
                                "Add to Cart",
                                variant="primary",
                                id="btn_add_to_cart",
                            )
                        yield Label("Cart:", classes="subtitle")
                        yield DataTable(id="inv_cart_table")
                        with Horizontal(classes="filter-row"):
                            yield Label("Cart Total: $0.00", id="inv_cart_total_lbl")
                            yield Button(
                                "Remove Selected",
                                variant="error",
                                id="btn_remove_from_cart",
                                disabled=True,
                            )
                            yield Button("Clear Cart", id="btn_clear_cart")

                    # Step 2: Add a custom line item not in the inventory list
                    with Collapsible(title="Step 2: Add Custom Item (Optional)", collapsed=True):
                        yield Label(
                            "Add charges not covered by the inventory above,"
                            " e.g. a workshop fee or donation."
                        )
                        yield Label("Item Name / Description:")
                        yield Input(
                            placeholder="e.g. Workshop fee, Donation",
                            id="pos_manual_desc",
                        )
                        yield Label("Price ($):")
                        yield Input(
                            placeholder="0.00",
                            id="pos_manual_price",
                            type="number",
                        )
                        with Horizontal(classes="filter-row"):
                            yield Button(
                                "Add Custom Item",
                                variant="primary",
                                id="btn_add_manual_to_cart",
                            )

                    # Step 3: Customer Details
                    with Collapsible(title="Step 3: Customer Details", collapsed=True):
                        yield Label(
                            "Search for an existing user to auto-fill, or"
                            " enter details manually:"
                        )
                        with Horizontal(classes="search-row"):
                            yield Input(
                                placeholder="Search by name or email...",
                                id="pos_customer_search_input",
                            )
                            yield Button(
                                "Search",
                                id="btn_pos_customer_search",
                            )
                        yield DataTable(id="pos_customer_search_table")

                        yield Label("Customer Name:")
                        yield Input(
                            placeholder="First and Last Name",
                            id="pos_customer_name",
                        )
                        yield Label(
                            "Customer Email (required to send a receipt for cash transactions):"
                        )
                        yield Input(
                            placeholder="customer@example.com",
                            id="pos_customer_email",
                        )
                        yield Label("Customer Phone (optional):")
                        yield Input(
                            placeholder="Phone number",
                            id="pos_customer_phone",
                        )

                    with Horizontal(classes="filter-row"):
                        yield Button(
                            pos_btn_label,
                            variant="success",
                            id="btn_process_manual_txn",
                        )
                        yield Button(
                            "Record Cash Transaction",
                            variant="warning",
                            id="btn_record_cash_txn",
                        )
                        yield Button(
                            "Clear Form",
                            id="btn_clear_pos_form",
                        )

                    with Collapsible(title="Recent Transactions", collapsed=True):
                        yield DataTable(id="pos_txns_table")
                        with Horizontal(classes="filter-row"):
                            yield Button(
                                "Refresh",
                                id="btn_refresh_pos_txns",
                            )
                            yield Button(
                                "Check Terminal Status",
                                variant="primary",
                                id="btn_check_pos_status",
                                disabled=True,
                            )
                            yield Button(
                                "Issue Refund",
                                variant="error",
                                id="btn_issue_refund",
                                disabled=True,
                            )

                # Subsection 1: Existing User Transactions (consolidated)
                with Collapsible(title="Membership Transactions", collapsed=True, classes="purchase-section"):
                    yield Label(
                        "Search for a user to manage their memberships, day passes, and credits:"
                    )
                    with Horizontal(classes="search-row"):
                        yield Input(
                            placeholder="Name or Email...",
                            id="user_search_input",
                        )
                        yield Button("Search", id="btn_user_search")
                    yield DataTable(id="user_search_table")
                    yield Label("Actions for Selected User:", classes="subtitle")
                    yield Label(
                        "Search for a user above to enable actions.",
                        classes="text-muted",
                        id="lbl_no_user_hint",
                    )
                    # Row 1: Membership actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Membership",
                            variant="success",
                            id="btn_add_mem",
                            disabled=True,
                        )
                        yield Button(
                            "Edit Memberships",
                            variant="primary",
                            id="btn_edit_mem",
                            disabled=True,
                        )
                    # Row 2: Day Pass actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Day Pass",
                            variant="success",
                            id="btn_add_daypass",
                            disabled=True,
                        )
                        yield Button(
                            "View Day Passes",
                            variant="primary",
                            id="btn_view_daypass",
                            disabled=True,
                        )
                    # Row 3: Credits actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            f"Add {currency} (+)",
                            variant="success",
                            id="btn_credit",
                            disabled=True,
                        )
                        yield Button(
                            f"Deduct {currency} (-)",
                            variant="error",
                            id="btn_debit",
                            disabled=True,
                        )
                        yield Button(
                            f"View {currency}",
                            variant="primary",
                            id="btn_view_credits",
                            disabled=True,
                        )
                    # Row 4: Square subscription actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Activate Square Membership Subscription",
                            variant="success",
                            id="btn_activate_subscription",
                            disabled=True,
                        )
                        yield Button(
                            "Cancel Subscription",
                            variant="error",
                            id="btn_cancel_subscription",
                            disabled=True,
                        )
                        yield Button(
                            "Poll Subscription Status",
                            variant="primary",
                            id="btn_poll_subscription",
                            disabled=True,
                        )

            # === REGULAR USER VIEW ===
            else:
                # Subsection 1: My Memberships
                with Collapsible(title="My Memberships", collapsed=False, classes="purchase-section"):
                    yield DataTable(id="my_mem_table")

                # Subsection 2: My Day Passes
                with Collapsible(title="My Day Passes", collapsed=False, classes="purchase-section"):
                    yield DataTable(id="my_daypass_table")

                # Subsection 3: My Consumables
                with Collapsible(title=f"My {currency} Ledger", collapsed=False, classes="purchase-section"):
                    yield Label(f"{currency} Balance: $0.00", id="my_balance_lbl")
                    yield DataTable(id="my_cons_table")

    def _compose_reports_tab(self) -> ComposeResult:
        """Yields widgets for the Reports tab."""
        yield Label("Membership Reports", classes="title")
        yield Label("(Click any row to Manage User)", classes="subtitle")

        yield Label("Filter by role:", classes="subtitle")
        with Horizontal(classes="filter-row"):
            yield Checkbox("Admin", value=True, id="chk_admin")
            yield Checkbox("Staff", value=True, id="chk_staff")
            yield Checkbox("Member (Active)", value=True, id="chk_member")
            yield Checkbox("Community (Inactive)", value=False, id="chk_community")
            yield Checkbox("Signed In", value=False, id="chk_signed_in")

        yield Button("Refresh Report", id="load_members")
        yield DataTable(id="members_table")

        yield Label("Export Options:", classes="subtitle")
        yield Button("Export CSV", id="btn_export_members_csv")
        yield Button("Export PDF", id="btn_export_members_pdf")

        yield Label("Admin and Statistics Reports:", classes="subtitle")
        yield Button(
            "Export Period Transaction Report",
            id="btn_period_transaction_report",
        )
        yield Button(
            "Export Period User Activity Report",
            id="btn_period_traction_report",
        )
        yield Button(
            "Export Community Contacts Report",
            id="btn_community_contacts_report",
        )
        yield Button(
            "Export Everything People CSV Report",
            id="btn_everything_people_csv",
        )

    def _compose_storage_tab(self) -> ComposeResult:
        """Yields widgets for the Storage tab."""
        with VerticalScroll():
            yield Label("Member Storage", classes="title")

            # Active storage assignments
            yield Label("Active Storage Assignments", classes="subtitle")
            yield DataTable(id="storage_active_table")
            with Horizontal(classes="filter-row"):
                yield Button(
                    "Assign Storage",
                    variant="success",
                    id="btn_storage_assign",
                )
                yield Button(
                    "View Selected",
                    id="btn_storage_view",
                    disabled=True,
                )
                yield Button(
                    "Edit Selected",
                    variant="primary",
                    id="btn_storage_edit",
                    disabled=True,
                )
                yield Button(
                    "Remove Selected (Archive)",
                    variant="error",
                    id="btn_storage_archive",
                    disabled=True,
                )
                yield Button("Refresh", id="btn_storage_refresh")

            # Archived storage assignments
            yield Label("Archived Storage Assignments", classes="subtitle")
            yield DataTable(id="storage_archived_table")

    def _compose_database_tab(self) -> ComposeResult:
        """Yields widgets for the Database tab."""
        sql_console_enabled = (
            services.get_setting("sql_console_enabled", "true").lower() == "true"
        )

        if not sql_console_enabled:
            yield Label(
                "SQL Console is disabled by the administrator.",
                classes="subtitle",
            )
        else:
            # --- LOCKED STATE VIEW ---
            with Center(id="db_lock_wrapper"):
                with Vertical(id="db_locked_view", classes="login-container"):
                    yield Label("SECURITY WARNING", classes="title error")
                    yield Label(
                        "You are accessing Raw SQL Controls.",
                        classes="subtitle",
                    )
                    yield Label(
                        "Bad commands can permanently DELETE or CORRUPT data.",
                        classes="error",
                    )
                    yield Label("Proceed with extreme caution.", classes="subtitle")

                    yield Input(
                        placeholder="Confirm Admin Password",
                        password=True,
                        id="db_pass_input",
                    )

                    yield Button("Unlock", variant="error", id="btn_verify_unlock")

            # --- UNLOCKED STATE VIEW (Hidden Initially) ---
            with Vertical(id="db_unlocked_view", classes="hidden"):
                yield Label("Raw SQL Execution (Danger Zone)", classes="title")

                with Vertical(classes="query-presets"):
                    yield Label("Common Queries (Click to Load):")
                    yield Button(
                        "1. Users with Medical/Allergy Info",
                        id="sql_q1",
                        classes="sql-btn",
                    )
                    yield Button(
                        "2. Emergency Contact List",
                        id="sql_q2",
                        classes="sql-btn",
                    )
                    yield Button(
                        "3. Members Missing Safety Orientation",
                        id="sql_q3",
                        classes="sql-btn",
                    )
                    yield Button(
                        "4. Count Users by Role",
                        id="sql_q4",
                        classes="sql-btn",
                    )
                    yield Button(
                        "5. Attendance Report (Date Range)",
                        id="sql_q5",
                        classes="sql-btn",
                    )

                yield Input(
                    placeholder="Enter custom SQL query here...",
                    id="sql_input",
                )
                yield Button("Execute SQL", variant="error", id="exec_sql_btn")

                yield Label("", id="sql_status")

                yield DataTable(id="sql_results")

                with Vertical(classes="export-section"):
                    yield Label("Export Options:", classes="subtitle")
                    yield Button("Export Results CSV", id="btn_export_sql_csv")
                    yield Button("Export Results PDF", id="btn_export_sql_pdf")

    def _compose_feedback_tab(self, user) -> ComposeResult:
        """Yields widgets for the Feedback tab."""
        yield Label("Submit Feedback / Bug Reports", classes="title")

        with Horizontal(classes="agreement-row"):
            yield Checkbox("General Feedback", id="chk_fb_general")
            yield Checkbox("Feature Request", id="chk_fb_feature")
            yield Checkbox("Bug Report", id="chk_fb_bug")
            yield Label("   ")
            yield Checkbox("URGENT", id="chk_fb_urgent")

        yield Input(placeholder="Type your comment here...", id="fb_comment")
        yield Button("Submit Feedback", variant="primary", id="btn_submit_feedback")

        # --- VISIBILITY RESTRICTION: Only Staff/Admin see the table and exports ---
        if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
            yield Label("Recent Submissions", classes="subtitle")
            yield DataTable(id="feedback_table")
            yield Button("Refresh List", id="btn_refresh_feedback")

            yield Label("Export Options:", classes="subtitle")
            yield Button("Export CSV", id="btn_export_fb_csv")
            yield Button("Export PDF", id="btn_export_fb_pdf")

    def _init_table(self, table_id, columns, cursor_type="row"):
        """Initialises a DataTable widget with the given columns and cursor type.

        Args:
            table_id: The DOM id of the DataTable (without '#' prefix).
            columns: Either a tuple of column name strings (simple add_columns)
                     or a list of (name, width) tuples (individual add_column).
            cursor_type: The cursor type to set on the table.
        """
        try:
            table = self.query_one(f"#{table_id}", DataTable)
        except Exception:
            return
        if isinstance(columns, list):
            # List of (name, width) tuples -- use individual add_column calls
            for col_name, col_width in columns:
                table.add_column(col_name, width=col_width)
        else:
            # Plain tuple of strings -- use add_columns
            table.add_columns(*columns)
        table.cursor_type = cursor_type

    def _build_dispatch(self):
        """Builds and returns the button ID to handler mapping for on_button_pressed."""
        return {
            "logout_btn": self._handle_logout,
            "signin_btn": self._handle_signin,
            "change_pwd_btn": lambda: self.app.push_screen(ChangePasswordScreen()),
            "edit_profile_btn": lambda: self.app.push_screen(
                EditProfileScreen(), self.refresh_profile
            ),
            "btn_staff_reg": lambda: self.app.push_screen(
                RegisterScreen(staff_mode=True)
            ),
            "btn_save_prefs": self.save_user_preferences,
            # Inventory cart handlers
            "btn_add_to_cart": self.add_to_cart,
            "btn_add_manual_to_cart": self.add_manual_to_cart,
            "btn_remove_from_cart": self.remove_from_cart,
            "btn_clear_cart": self.clear_cart,
            # Storage tab handlers
            "btn_storage_assign": self.open_storage_assign_modal,
            "btn_storage_view": self.open_storage_view_modal,
            "btn_storage_edit": self.open_storage_edit_modal,
            "btn_storage_archive": self.archive_storage_assignment,
            "btn_storage_refresh": self.load_storage_assignments,
            # Feedback handlers
            "btn_submit_feedback": self.submit_feedback_action,
            "btn_refresh_feedback": self.load_feedback,
            "btn_export_fb_csv": lambda: self.initiate_export(
                "#feedback_table", "feedback_report", "csv", full_feedback=True
            ),
            "btn_export_fb_pdf": lambda: self.initiate_export(
                "#feedback_table", "feedback_report", "pdf", full_feedback=True
            ),
            # Pending / members
            "refresh_pending": self._handle_refresh_pending,
            "load_members": self.load_members,
            "approve_btn": self._handle_approve,
            # Staff tool search
            "btn_staff_user_search": self.action_staff_user_search,
            # Database lock
            "btn_verify_unlock": self.verify_database_unlock,
            # SQL execution
            "exec_sql_btn": lambda: self.run_raw_sql(
                self.query_one("#sql_input").value
            ),
            # Export handlers
            "btn_export_members_csv": lambda: self.initiate_export(
                "#members_table", "members_report", "csv"
            ),
            "btn_export_members_pdf": lambda: self.initiate_export(
                "#members_table", "members_report", "pdf"
            ),
            "btn_export_sql_csv": lambda: self.initiate_export(
                "#sql_results", "sql_query_result", "csv"
            ),
            "btn_export_sql_pdf": lambda: self.initiate_export(
                "#sql_results", "sql_query_result", "pdf"
            ),
            "btn_period_transaction_report": lambda: self.app.push_screen(
                PeriodTransactionReportModal()
            ),
            "btn_period_traction_report": lambda: self.app.push_screen(
                PeriodTractionReportModal()
            ),
            "btn_community_contacts_report": lambda: self.app.push_screen(
                CommunityContactsReportModal()
            ),
            "btn_everything_people_csv": self.initiate_everything_people_csv,
            # Unified user search
            "btn_user_search": self.action_search_users,
            # Membership actions
            "btn_add_mem": self._handle_add_mem,
            "btn_edit_mem": self._handle_edit_mem,
            # Day pass actions
            "btn_add_daypass": self._handle_add_daypass,
            "btn_view_daypass": self._handle_view_daypass,
            # Credits actions
            "btn_credit": self._handle_credit,
            "btn_debit": self._handle_debit,
            "btn_view_credits": self._handle_view_credits,
            # Square subscription actions
            "btn_activate_subscription": self._handle_activate_subscription,
            "btn_cancel_subscription": self._handle_cancel_subscription,
            "btn_poll_subscription": self._handle_poll_subscription,
            # POS customer search
            "btn_pos_customer_search": self.action_pos_customer_search,
            # POS / manual transaction actions
            "btn_process_manual_txn": self.process_manual_transaction,
            "btn_record_cash_txn": self.record_cash_transaction,
            "btn_clear_pos_form": self.clear_pos_form,
            "btn_refresh_pos_txns": self.load_pos_transactions,
            "btn_check_pos_status": self.check_pos_terminal_status,
            "btn_issue_refund": self._handle_issue_refund,
        }

    # --- Small handler methods extracted from on_button_pressed inline logic ---

    def _handle_logout(self):
        """Logs the current user out and returns to the previous screen."""
        self.app.current_user = None
        self.app.pop_screen()

    def _handle_signin(self):
        """Handles sign-in/sign-out toggle for the current user."""
        acct = self.app.current_user.account_number
        try:
            if services.is_user_signed_in(acct):
                self.app.push_screen(ConfirmSignOutScreen(), self.on_signout_confirm)
            else:
                # Use the user's preferred visit type if set, otherwise show the selector
                pref_type = services.get_user_preference(
                    acct, "preferred_visit_type", ""
                )
                if pref_type:
                    self.on_visit_type_selected(acct, pref_type)
                else:
                    self.app.push_screen(
                        SelectVisitTypeModal(),
                        partial(self.on_visit_type_selected, acct),
                    )
        except ValueError as e:
            self.app.notify(str(e), severity="error")

    def _handle_refresh_pending(self):
        """Refreshes the pending approvals list and alert banner."""
        self.load_pending()
        self.update_pending_alert()

    def _handle_approve(self):
        """Approves the currently selected pending user account."""
        table = self.query_one("#pending_table")
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            row_data = table.get_row(row_key)
            acct_num = int(row_data[0])
            services.approve_user(self.app.current_user.account_number, acct_num)
            self.app.notify(f"Approved User {acct_num}")
            self.load_pending()
            self.update_pending_alert()
        except Exception:
            self.app.notify("Select a user first", severity="warning")

    def _handle_add_mem(self):
        """Opens the Add Membership modal for the selected user."""
        if self.selected_user_acct:
            self.app.push_screen(
                AddMembershipModal(self.selected_user_acct),
                self._refresh_user_table,
            )

    def _handle_edit_mem(self):
        """Opens the Manage Memberships modal for the selected user."""
        if self.selected_user_acct:
            self.app.push_screen(ManageMembershipsModal(self.selected_user_acct))

    def _handle_add_daypass(self):
        """Opens the Add Day Pass modal for the selected user."""
        if self.selected_user_acct:
            self.app.push_screen(
                AddDayPassModal(self.selected_user_acct), self._refresh_user_table
            )

    def _handle_view_daypass(self):
        """Opens the Day Pass History modal for the selected user."""
        if self.selected_user_acct:
            self.app.push_screen(DayPassHistoryModal(self.selected_user_acct))

    def _handle_credit(self):
        """Opens the credit transaction modal for the selected user."""
        if self.selected_user_acct:
            currency = services.get_setting("app_currency_name", "Credits")
            self.app.push_screen(
                TransactionModal(self.selected_user_acct, "credit", currency),
                self._refresh_user_table,
            )

    def _handle_debit(self):
        """Opens the debit transaction modal for the selected user."""
        if self.selected_user_acct:
            currency = services.get_setting("app_currency_name", "Credits")
            self.app.push_screen(
                TransactionModal(self.selected_user_acct, "debit", currency),
                self._refresh_user_table,
            )

    def _handle_view_credits(self):
        """Opens the View Credits modal for the selected user."""
        if self.selected_user_acct:
            currency = services.get_setting("app_currency_name", "Credits")
            self.app.push_screen(ViewCreditsModal(self.selected_user_acct, currency))

    def _handle_activate_subscription(self):
        """Opens the Activate Subscription modal for the selected user."""
        if self.selected_user_acct:
            self.app.push_screen(
                ActivateSubscriptionModal(self.selected_user_acct),
                self._refresh_user_table,
            )

    def _handle_cancel_subscription(self):
        """Cancels the Square subscription for the selected user."""
        if self.selected_user_acct:
            ok, msg = square_service.cancel_square_subscription(self.selected_user_acct)
            severity = "information" if ok else "error"
            self.app.notify(msg, severity=severity)

    def _handle_poll_subscription(self):
        """Polls the Square subscription status for the selected user."""
        if self.selected_user_acct:
            ok, msg = square_service.poll_member_subscription(self.selected_user_acct)
            severity = "information" if ok else "error"
            self.app.notify(msg, severity=severity)

    def on_mount(self):
        user = self.app.current_user
        currency = services.get_setting("app_currency_name", "Credits")
        self.update_signin_button()

        # Reset mutable instance state so it is never shared across logins
        self._cart = []
        self._inv_selected_item = None
        self._inv_selected_cart_key = None
        self._manual_entry_counter = 0

        # Build button dispatch table for on_button_pressed
        self._dispatch = self._build_dispatch()

        # Initialize Security Timer -- read timeout from DB, fall back to class default
        try:
            self.AUTO_LOGOUT_SECONDS = (
                int(services.get_setting("logout_timeout_minutes", "10")) * 60
            )
        except ValueError:
            pass  # Keep the class-level default if the stored value is invalid
        self.last_activity = time.time()
        self.set_interval(1.0, self.update_security_timer)

        # Initialize tables using the configuration list
        # Only init tables that exist in the current DOM (role-dependent tabs
        # may not have rendered all tables)
        for cfg in self._TABLE_CONFIGS:
            self._init_table(cfg["id"], cfg["columns"], cfg.get("cursor_type", "row"))

        # Initialize Feedback data ONLY if visible
        if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
            self.load_feedback()

        # Permissions check for Staff/Admin data loading
        if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
            self.load_pos_transactions()
            self._load_inv_available_table()
            self.load_storage_assignments()

            self.load_pending()
            self.load_members()
            self.update_pending_alert()
        else:
            # === INITIALIZE USER TABLES FOR NON-STAFF ===
            self.init_user_purchases_view(user.account_number)

        # Separate Permissions check for Database Table (Admin Only, SQL console enabled)
        if user.role == models.UserRole.ADMIN:
            sql_table = self.query("#sql_results")
            if sql_table:
                sql_table.first(DataTable).cursor_type = "row"

        # Load user preferences and profile data into the My Profile tab widgets
        acct = user.account_number

        balance = services.get_user_balance(acct)
        self.query_one("#lbl_balance").update(f"{currency} Balance: ${balance:.2f}")

        pref_visit = services.get_user_preference(acct, "preferred_visit_type", "")
        try:
            self.query_one("#pref_visit_type", Select).value = pref_visit
        except Exception:
            pass

    def init_user_purchases_view(self, acct_num: int):
        """Loads data for the standard user purchases view."""
        # 1. Memberships
        mem_table = self.query_one("#my_mem_table", DataTable)
        if mem_table:
            mem_table.add_columns("Start Date", "End Date")
            mems = services.get_user_memberships(acct_num)
            for m in mems:
                mem_table.add_row(
                    m.start_date.strftime("%Y-%m-%d"), m.end_date.strftime("%Y-%m-%d")
                )

        # 2. Day Passes
        dp_table = self.query_one("#my_daypass_table", DataTable)
        if dp_table:
            dp_table.add_columns("Date", "Description")
            passes = services.get_user_day_passes(acct_num)
            for p in passes:
                dp_table.add_row(p.date.strftime("%Y-%m-%d"), p.description)

        # 3. Consumables
        cons_table = self.query_one("#my_cons_table", DataTable)
        if cons_table:
            cons_table.add_columns("Date", "Type", "Amount", "Description")
            txns = services.get_user_transactions(acct_num)
            for t in txns:
                cons_table.add_row(
                    t.date.strftime("%Y-%m-%d"),
                    t.credit_debit.title(),
                    f"${t.credits:.2f}",
                    t.description or "",
                )

        # Update Balance Label
        balance = services.get_user_balance(acct_num)
        currency = services.get_setting("app_currency_name", "Credits")
        self.query_one("#my_balance_lbl").update(f"{currency} Balance: ${balance:.2f}")

    # ... Inactivity Trackers ...
    def reset_activity(self):
        self.last_activity = time.time()

    def on_key(self, event: events.Key) -> None:
        self.reset_activity()

    def on_click(self, event: events.Click) -> None:
        self.reset_activity()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        self.reset_activity()

    def update_security_timer(self):
        elapsed = time.time() - self.last_activity
        remaining = max(0, self.AUTO_LOGOUT_SECONDS - elapsed)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        label = self.query_one("#logout_timer")
        label.update(f"Auto-logout: {minutes:02}:{seconds:02}")

        if remaining < 60:
            label.add_class("urgent")
        else:
            label.remove_class("urgent")

        if remaining <= 0:
            self.perform_auto_logout()

    def perform_auto_logout(self):
        self.app.notify("Session Timed Out due to inactivity.", severity="warning")
        self.app.current_user = None

        # Local import to avoid circular dependency
        from screens.login import LoginScreen

        # Pop screens until we reach the LoginScreen or the base
        # This prevents popping the LoginScreen itself
        while len(self.app.screen_stack) > 1:
            if isinstance(self.app.screen, LoginScreen):
                return
            self.app.pop_screen()

        # Fallback: if we are here and not on LoginScreen, ensure we go there
        if not isinstance(self.app.screen, LoginScreen):
            self.app.push_screen(LoginScreen())

    # ... Rest of methods ...
    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "members_table":
            row_data = event.data_table.get_row(event.row_key)
            acct_num = str(row_data[0])
            name = str(row_data[1])
            self.app.push_screen(
                MemberActionModal(acct_num, name), self.refresh_after_manage
            )

        elif event.data_table.id == "staff_user_search_table":
            # Just like members_table, open the MemberActionModal
            row_data = event.data_table.get_row(event.row_key)
            acct_num = str(row_data[0])
            name = str(row_data[1])
            self.app.push_screen(
                MemberActionModal(acct_num, name), self.refresh_after_manage
            )

        elif event.data_table.id == "feedback_table":
            row_data = event.data_table.get_row(event.row_key)
            fb_id = int(row_data[0])
            # Refresh feedback list after modal closes (in case of delete/update)
            self.app.push_screen(
                FeedbackViewModal(fb_id), self.refresh_feedback_after_modal
            )

        elif event.data_table.id == "user_search_table":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_user_acct = int(row_data[0])
            for btn_id in (
                "btn_add_mem",
                "btn_edit_mem",
                "btn_add_daypass",
                "btn_view_daypass",
                "btn_credit",
                "btn_debit",
                "btn_view_credits",
            ):
                self.query_one(f"#{btn_id}").disabled = False
            # Subscription buttons are only usable when Square is enabled.
            square_active = square_service.get_pos_config().square_enabled
            for btn_id in (
                "btn_activate_subscription",
                "btn_cancel_subscription",
                "btn_poll_subscription",
            ):
                self.query_one(f"#{btn_id}").disabled = not square_active
            self.app.notify(f"Selected: {row_data[1]}")

        elif event.data_table.id == "pos_customer_search_table":
            # Auto-fill customer detail fields from the selected user row
            row_data = event.data_table.get_row(event.row_key)
            self.query_one("#pos_customer_name", Input).value = str(row_data[1])
            self.query_one("#pos_customer_email", Input).value = str(row_data[2])
            self.query_one("#pos_customer_phone", Input).value = str(row_data[3])
            self.app.notify(f"Customer details filled: {row_data[1]}")

        elif event.data_table.id == "pos_txns_table":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_pos_txn_id = int(row_data[0])
            # Only enable status check for Square transactions (not local records)
            via = str(row_data[6])
            self.query_one("#btn_check_pos_status").disabled = via != "Square"
            # Disable refund if already refunded (Status column)
            already_refunded = str(row_data[5]).strip().lower() == "refunded"
            self.query_one("#btn_issue_refund").disabled = already_refunded
            self.app.notify(f"Selected transaction #{self.selected_pos_txn_id}")

        elif event.data_table.id == "inv_available_table":
            row_data = event.data_table.get_row(event.row_key)
            self._inv_selected_item = {
                "id": int(row_data[0]),
                "name": str(row_data[1]),
                "price": float(str(row_data[3]).lstrip("$")),
            }

        elif event.data_table.id == "inv_cart_table":
            # Row key is a string ("inv_{id}" or "manual_{counter}") set when adding rows
            self._inv_selected_cart_key = event.row_key.value
            self.query_one("#btn_remove_from_cart").disabled = False

        elif event.data_table.id == "storage_active_table":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_storage_assignment_id = int(row_data[0])
            self.query_one("#btn_storage_view").disabled = False
            self.query_one("#btn_storage_edit").disabled = False
            self.query_one("#btn_storage_archive").disabled = False

    def refresh_feedback_after_modal(self, result: bool = False):
        self.load_feedback()

    def refresh_after_manage(self, result: bool = False):
        if result:
            self.load_members()

    def refresh_profile(self, result: bool = False):
        if result:
            user = self.app.current_user

            # Safe role access for refresh
            role_val = (
                user.role.value if hasattr(user.role, "value") else str(user.role)
            )
            role_name = user.role.name if hasattr(user.role, "name") else str(user.role)

            self.query_one("#welcome_lbl").update(
                f"Welcome, {role_val.title()} {user.first_name}!"
            )
            self.query_one("#lbl_role").update(f"Account Type: {role_name}")
            self.query_one("#lbl_acct").update(f"Account #: {user.account_number}")
            balance = services.get_user_balance(user.account_number)
            currency = services.get_setting("app_currency_name", "Credits")
            self.query_one("#lbl_balance").update(f"{currency} Balance: ${balance:.2f}")

    def update_signin_button(self):
        btn = self.query_one("#signin_btn", Button)
        tag = (
            services.get_setting("tag_name", settings.TAG_NAME)
            or settings.TAG_NAME
            or "Makerspace"
        )
        if services.is_user_signed_in(self.app.current_user.account_number):
            btn.label = f"Sign Out of {tag}"
            btn.variant = "warning"
        else:
            btn.label = f"Sign In to {tag}"
            btn.variant = "success"

    def update_pending_alert(self):
        pending_count = len(services.get_pending_users())
        alert = self.query_one("#pending_alert")

        if pending_count > 0:
            alert.update(
                f"[!]  ACTION REQUIRED: {pending_count} User(s) Awaiting Approval"
            )
            alert.remove_class("hidden")
            alert.add_class("warning-banner")
        else:
            alert.add_class("hidden")
            alert.remove_class("warning-banner")

    def on_input_submitted(self, event: Input.Submitted):
        self.reset_activity()
        if event.input.id == "db_pass_input":
            self.verify_database_unlock()
        elif event.input.id == "sql_input":
            query = self.query_one("#sql_input").value
            self.run_raw_sql(query)
        elif event.input.id == "user_search_input":
            self.action_search_users()
        elif event.input.id == "staff_user_search_input":
            self.action_staff_user_search()
        elif event.input.id == "pos_customer_search_input":
            self.action_pos_customer_search()

    MEMBER_FILTER_CHECKBOXES = {
        "chk_admin",
        "chk_staff",
        "chk_member",
        "chk_community",
        "chk_signed_in",
    }
    FEEDBACK_FILTER_CHECKBOXES = {
        "chk_fb_general",
        "chk_fb_feature",
        "chk_fb_bug",
        "chk_fb_urgent",
    }

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Reload the relevant table whenever a filter checkbox is toggled."""
        checkbox_id = event.checkbox.id
        if checkbox_id in self.MEMBER_FILTER_CHECKBOXES:
            self.load_members()
        elif checkbox_id in self.FEEDBACK_FILTER_CHECKBOXES:
            self.load_feedback()

    def on_button_pressed(self, event: Button.Pressed):
        self.reset_activity()
        btn_id = event.button.id

        # Check SQL presets first
        if btn_id in self._SQL_PRESETS:
            self.query_one("#sql_input").value = self._SQL_PRESETS[btn_id]
            return

        handler = self._dispatch.get(btn_id)
        if handler:
            handler()

    def action_pos_customer_search(self):
        """Search for existing users to auto-fill POS customer details."""
        query = self.query_one("#pos_customer_search_input").value.strip()
        table = self.query_one("#pos_customer_search_table", DataTable)
        table.clear()

        if not query:
            self.app.notify("Please enter a search term.", severity="error")
            return

        results = services.search_users(query)
        if not results:
            self.app.notify("No users found.", severity="warning")
            return

        for u in results:
            table.add_row(
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                u.email,
                u.phone or "",
            )

    def action_staff_user_search(self):
        query = self.query_one("#staff_user_search_input").value.strip()
        table = self.query_one("#staff_user_search_table", DataTable)
        table.clear()

        if not query:
            self.app.notify("Please enter a search term.", severity="error")
            return

        results = services.search_users(query)
        if not results:
            self.app.notify("No users found.", severity="warning")
            return

        for u in results:
            table.add_row(
                str(u.account_number), f"{u.first_name} {u.last_name}", u.email
            )

    def action_search_users(self):
        """Search for users for the unified Existing User Transactions section."""
        query = self.query_one("#user_search_input").value.strip()
        table = self.query_one("#user_search_table", DataTable)
        table.clear()
        self.selected_user_acct = None
        for btn_id in (
            "btn_add_mem",
            "btn_edit_mem",
            "btn_add_daypass",
            "btn_view_daypass",
            "btn_credit",
            "btn_debit",
            "btn_view_credits",
            "btn_activate_subscription",
            "btn_cancel_subscription",
            "btn_poll_subscription",
        ):
            self.query_one(f"#{btn_id}").disabled = True
        if not query:
            self.app.notify("Please enter a search term.", severity="error")
            return
        results = services.search_users(query)
        if not results:
            self.app.notify("No users found.", severity="warning")
            return
        for u in results:
            table.add_row(
                str(u.account_number), f"{u.first_name} {u.last_name}", u.email
            )

    def _refresh_user_table(self, result: bool):
        """Re-run the user search after any action that modifies user data."""
        if result:
            self.action_search_users()

    def verify_database_unlock(self):
        # Defence-in-depth: re-check the setting at unlock time in case it was changed
        # by another admin session while this user is already logged in.
        if services.get_setting("sql_console_enabled", "true").lower() != "true":
            self.app.notify(
                "SQL Console is disabled by the administrator.", severity="error"
            )
            return

        pwd = self.query_one("#db_pass_input").value
        user = self.app.current_user
        if verify_password(pwd, user.password_hash):
            self.query_one("#db_lock_wrapper").add_class("hidden")
            self.query_one("#db_unlocked_view").remove_class("hidden")
            self.app.notify("Database Tools Unlocked - BE CAREFUL", severity="warning")
        else:
            self.app.notify("Incorrect Password", severity="error")
            self.query_one("#db_pass_input").value = ""

    def initiate_export(
        self, table_id: str, base_name: str, fmt: str, full_feedback: bool = False
    ):
        def on_directory_selected(path: str | None):
            if path:
                self.do_export(table_id, base_name, fmt, path, full_feedback)

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def initiate_everything_people_csv(self):
        """Opens the directory selector then writes the full people data CSV."""

        def on_directory_selected(path: str | None):
            if not path:
                return
            try:
                sections = services.get_everything_people_data()
                filename = exporters.get_timestamp_filename("everything_people", "csv")
                saved = exporters.export_period_report_to_csv(filename, sections, path)
                self.app.notify(f"Exported to: {saved}")
            except Exception as e:
                self.app.notify(f"Export Failed: {str(e)}", severity="error")

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def do_export(
        self,
        table_id: str,
        base_name: str,
        fmt: str,
        output_dir: str,
        full_feedback: bool = False,
    ):
        try:
            if full_feedback:
                # Fetch full feedback data from database instead of UI
                fbs = services.get_all_feedback()
                # Added Admin Response to export
                headers = [
                    "ID",
                    "Date",
                    "Name",
                    "Urgent",
                    "Full Comment",
                    "Admin Response",
                ]
                rows = []
                for f in fbs:
                    urgent_mark = "[!]" if f.urgent else ""
                    rows.append(
                        [
                            str(f.id),
                            str(f.submitted_at),
                            f"{f.first_name} {f.last_name}",
                            urgent_mark,
                            f.comment,
                            f.admin_response or "",  # Added Response field
                        ]
                    )
            else:
                table = self.query_one(table_id, DataTable)
                headers = [str(c.label) for c in table.columns.values()]
                rows = []
                for row_key in table.rows:
                    rows.append(table.get_row(row_key))

            if not rows:
                self.app.notify("No data to export!", severity="warning")
                return

            filename = exporters.get_timestamp_filename(base_name, fmt)
            path = ""
            if fmt == "csv":
                path = exporters.export_to_csv(filename, headers, rows, output_dir)
            elif fmt == "pdf":
                header_text = services.get_setting("report_header_text", "")
                path = exporters.export_to_pdf(
                    filename,
                    base_name.replace("_", " ").upper(),
                    headers,
                    rows,
                    output_dir,
                    header_text=header_text,
                )
            self.app.notify(f"Exported to: {path}")
        except Exception as e:
            self.app.notify(f"Export Failed: {str(e)}", severity="error")

    # ---------------------------------------------------------------------------
    # POS / Manual Transaction methods
    # ---------------------------------------------------------------------------

    def load_pos_transactions(self):
        """
        Refreshes any pending Square Terminal checkouts from the API, then loads
        the 50 most recent SquareTransaction records into the POS table.

        Refreshing before loading ensures that auto-cancelled checkouts (Square
        cancels unattended terminals after ~5 minutes) are shown with the correct
        status rather than remaining stuck on 'Pending' or 'In Progress'.
        """
        square_service.refresh_pending_transactions()
        try:
            table = self.query_one("#pos_txns_table", DataTable)
        except Exception:
            return
        table.clear()
        self.selected_pos_txn_id = None
        try:
            self.query_one("#btn_check_pos_status").disabled = True
        except Exception:
            pass
        try:
            self.query_one("#btn_issue_refund").disabled = True
        except Exception:
            pass

        txns = square_service.get_recent_transactions(limit=50)
        for t in txns:
            # Determine the "Via" display based on payment method and status
            if t.square_status == "cash_square":
                via = "Cash (Square)"
            elif t.square_status == "cash":
                via = "Cash"
            elif t.is_local:
                via = "Local"
            else:
                via = "Square"
            status = "Refunded" if t.refund_status == "refunded" else t.square_status.replace("_", " ").title()
            table.add_row(
                str(t.id),
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.customer_name or "",
                f"${t.amount:.2f}",
                (t.description or "")[:24],
                status,
                via,
                t.processed_by or "",
                t.refunded_by or "",
                (t.refund_reason or "")[:22],
            )

    def process_manual_transaction(self):
        """
        Reads the manual transaction form, validates inputs, and either sends a
        checkout request to the Square Terminal or records a local transaction
        depending on whether Square is enabled in POS settings.
        """
        if not self._cart:
            self.app.notify(
                "Cart is empty. Add items before processing.", severity="error"
            )
            return

        try:
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        amount = sum(e["qty"] * e["unit_price"] for e in self._cart)
        desc_parts = [
            f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
            for e in self._cart
        ]
        description = ", ".join(desc_parts)

        staff = self.app.current_user
        staff_name = f"{staff.first_name} {staff.last_name}" if staff else None
        ok, message, txn = square_service.process_terminal_checkout(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
            processed_by=staff_name,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            # Only send a receipt when a real payment was submitted to Square.
            # is_local=True means Square was disabled and nothing was actually
            # charged -- the record is an audit placeholder, not a payment confirmation.
            if ok and not txn.is_local and txn.customer_email:
                try:
                    hackspace_name = services.get_setting("hackspace_name", "Nucleus")
                    sent = send_transaction_receipt(
                        txn_id=txn.id,
                        amount=txn.amount,
                        customer_name=txn.customer_name,
                        customer_email=txn.customer_email,
                        description=txn.description or "",
                        payment_method="Card (Square Terminal)",
                        transaction_ref=txn.square_checkout_id or "",
                        transaction_date=txn.created_at.strftime("%Y-%m-%d %H:%M"),
                        subject_override=f"{hackspace_name} - Payment Submitted #{txn.id}",
                    )
                    if sent:
                        self.app.notify(f"Receipt emailed to {txn.customer_email}.")
                except Exception as exc:
                    self.app.notify(f"Receipt email failed: {exc}", severity="warning")
            self.clear_pos_form()
            self.load_pos_transactions()

    def record_cash_transaction(self):
        """
        Reads the manual transaction form and records a cash payment either to
        Square (if enabled and configured) or locally. When recorded in Square,
        the transaction appears in Square Dashboard so the bookkeeper only needs
        to reconcile one system.
        """
        if not self._cart:
            self.app.notify(
                "Cart is empty. Add items before recording.", severity="error"
            )
            return

        try:
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        amount = sum(e["qty"] * e["unit_price"] for e in self._cart)
        desc_parts = [
            f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
            for e in self._cart
        ]
        description = ", ".join(desc_parts)

        staff = self.app.current_user
        staff_name = f"{staff.first_name} {staff.last_name}" if staff else None
        ok, message, txn = square_service.record_cash_payment(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
            processed_by=staff_name,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            if ok and txn.customer_email:
                try:
                    sent = send_transaction_receipt(
                        txn_id=txn.id,
                        amount=txn.amount,
                        customer_name=txn.customer_name,
                        customer_email=txn.customer_email,
                        description=txn.description or "",
                        payment_method="Cash",
                        transaction_ref=txn.square_checkout_id or "",
                        transaction_date=txn.created_at.strftime("%Y-%m-%d %H:%M"),
                    )
                    if sent:
                        self.app.notify(f"Receipt emailed to {txn.customer_email}.")
                except Exception as exc:
                    self.app.notify(f"Receipt email failed: {exc}", severity="warning")
            self.clear_pos_form()
            self.load_pos_transactions()

    def clear_pos_form(self):
        """Resets all manual transaction input fields and the inventory cart."""
        for field_id in (
            "pos_amount",
            "pos_customer_name",
            "pos_customer_email",
            "pos_customer_phone",
            "pos_description",
            "pos_customer_search_input",
        ):
            try:
                self.query_one(f"#{field_id}", Input).value = ""
            except Exception:
                pass
        try:
            self.query_one("#pos_customer_search_table", DataTable).clear()
        except Exception:
            pass
        self.clear_cart()

    def check_pos_terminal_status(self):
        """
        Queries Square for the current status of the selected transaction and
        updates the local record. Only applicable to Square-processed transactions.
        """
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return
        ok, message = square_service.update_transaction_status(self.selected_pos_txn_id)
        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)
        if ok:
            self.load_pos_transactions()

    def _handle_issue_refund(self):
        """
        Opens the refund confirmation modal for the selected transaction.
        On confirmation, processes the refund and refreshes the table.
        """
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return
        txn = square_service.get_transaction_by_id(self.selected_pos_txn_id)
        if not txn:
            self.app.notify("Transaction not found.", severity="error")
            return

        def on_refund_confirmed(reason: str | None) -> None:
            if not reason:
                return
            staff = self.app.current_user
            staff_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown"
            ok, message = square_service.process_refund(
                txn_id=self.selected_pos_txn_id,
                reason=reason,
                refunded_by=staff_name,
            )
            self.app.notify(message, severity="information" if ok else "error")
            if ok:
                self.load_pos_transactions()

        self.app.push_screen(
            RefundConfirmModal(txn.id, txn.amount, txn.customer_name or ""),
            on_refund_confirmed,
        )

    def save_user_preferences(self):
        """Reads and persists the current user's My Preferences widgets to UserPreference."""
        acct = self.app.current_user.account_number
        try:
            visit_pref = self.query_one("#pref_visit_type", Select).value
            # Select.BLANK is returned when the first (no preference) option is chosen
            if visit_pref is Select.BLANK:
                visit_pref = ""
            services.set_user_preference(acct, "preferred_visit_type", visit_pref or "")
            self.app.notify("Preferences saved.")
        except Exception as e:
            self.app.notify(f"Error saving preferences: {str(e)}", severity="error")

    def on_visit_type_selected(self, acct: int, visit_type):
        """Callback from SelectVisitTypeModal. Records the sign-in with the chosen visit type."""
        if visit_type is None:
            return  # User cancelled -- do not sign in
        try:
            services.sign_in_user(acct, str(visit_type))
            self.update_signin_button()

            self.app.push_screen(
                PostActionCountdownModal("Signed In Successfully. Happy Making!"),
                self._on_countdown_result,
            )
        except ValueError as e:
            self.app.notify(str(e), severity="error")

    def on_signout_confirm(self, result: bool):
        if result:
            acct = self.app.current_user.account_number
            try:
                services.sign_out_user(acct)
                self.update_signin_button()
                self.app.push_screen(
                    PostActionCountdownModal("Signed Out Successfully. Goodbye!"),
                    self._on_countdown_result,
                )
            except ValueError as e:
                self.app.notify(str(e), severity="error")

    def _on_countdown_result(self, stay: bool):
        """Called when PostActionCountdownModal closes. Log out unless user chose to stay."""
        if stay:
            self.reset_activity()
        else:
            self.perform_auto_logout()

    def load_feedback(self):
        try:
            table = self.query_one("#feedback_table", DataTable)
        except Exception:
            return  # Table not present (user not staff/admin)

        table.clear()
        fbs = services.get_all_feedback()
        for f in fbs:
            urgent_mark = "[!]" if f.urgent else ""
            preview = (f.comment[:50] + "...") if len(f.comment) > 50 else f.comment
            response_preview = (
                (f.admin_response[:30] + "...")
                if (f.admin_response and len(f.admin_response) > 30)
                else (f.admin_response or "")
            )
            table.add_row(
                str(f.id),
                str(f.submitted_at),
                f"{f.first_name} {f.last_name}",
                urgent_mark,
                preview,
                response_preview,  # Added response column
            )

    def submit_feedback_action(self):
        user = self.app.current_user
        comment = self.query_one("#fb_comment").value
        if not comment:
            self.app.notify("Please enter a comment.", severity="error")
            return
        prefixes = []
        if self.query_one("#chk_fb_general").value:
            prefixes.append("[Feedback]")
        if self.query_one("#chk_fb_feature").value:
            prefixes.append("[Feature Request]")
        if self.query_one("#chk_fb_bug").value:
            prefixes.append("[Bug Report]")

        # New check: ensure at least one feedback type is selected
        if not prefixes:
            self.app.notify(
                "Please select a feedback type (General, Feature, or Bug).",
                severity="error",
            )
            return

        full_comment = " ".join(prefixes) + " " + comment
        urgent = self.query_one("#chk_fb_urgent").value
        services.submit_feedback(
            user.account_number,
            user.first_name,
            user.last_name,
            urgent,
            full_comment,
        )
        self.app.notify("Feedback Submitted!")
        self.query_one("#fb_comment").value = ""
        self.query_one("#chk_fb_general").value = False
        self.query_one("#chk_fb_feature").value = False
        self.query_one("#chk_fb_bug").value = False
        self.query_one("#chk_fb_urgent").value = False
        self.load_feedback()

    # ... rest of methods like load_pending, load_members, run_raw_sql ...
    def load_pending(self):
        table = self.query_one("#pending_table")
        table.clear()
        users = services.get_pending_users()
        for u in users:
            table.add_row(
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                u.email,
                str(u.joined_date),
            )

    def load_members(self):
        table = self.query_one("#members_table")
        table.clear()
        roles_to_fetch = []
        if self.query_one("#chk_admin").value:
            roles_to_fetch.append("admin")
        if self.query_one("#chk_staff").value:
            roles_to_fetch.append("staff")
        if self.query_one("#chk_member").value:
            roles_to_fetch.append("member")
        if self.query_one("#chk_community").value:
            roles_to_fetch.append("community")

        # Collect users from each active filter, deduplicating by account number.
        # "Signed In" is additive -- it unions currently signed-in users with the
        # role-filtered results rather than restricting them.
        users_by_acct = {}
        if roles_to_fetch:
            for u in services.get_users(roles_to_fetch):
                users_by_acct[u.account_number] = u
        if self.query_one("#chk_signed_in").value:
            for u in services.get_signed_in_users():
                users_by_acct[u.account_number] = u

        if not users_by_acct:
            return

        for u in users_by_acct.values():
            # FIX: Handle string vs Enum role safely
            role_display = (
                u.role.name if hasattr(u.role, "name") else str(u.role).upper()
            )
            table.add_row(
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                role_display,
                u.email,
            )

    def run_raw_sql(self, query: str):
        if not query.strip():
            self.app.notify("Please enter a SQL query", severity="error")
            return
        result = services.execute_raw_sql(query)
        status_lbl = self.query_one("#sql_status")
        table = self.query_one("#sql_results")
        table.clear(columns=True)
        if result["success"]:
            if result["type"] == "select":
                status_lbl.update(f"Success: Returned {len(result['rows'])} rows.")
                table.add_columns(*result["headers"])
                table.add_rows(result["rows"])
            else:
                status_lbl.update(f"Success: Affected {result['rows_affected']} rows.")
        else:
            status_lbl.update(f"Error: {result['error']}")

    # --- Storage Tab ---

    def load_storage_assignments(self):
        """Loads active and archived assignment rows into the Storage tab tables."""
        try:
            active_table = self.query_one("#storage_active_table", DataTable)
            archived_table = self.query_one("#storage_archived_table", DataTable)
        except Exception:
            return

        active_table.clear()
        for a in services.get_active_storage_assignments():
            unit = services.get_storage_unit_by_id(a.unit_id)
            unit_label = unit.unit_number if unit else str(a.unit_id)
            name = a.assigned_to_name or ""
            total = f"${a.charge_total:.2f}" if a.charge_total is not None else ""
            active_table.add_row(
                str(a.id),
                unit_label,
                name,
                a.item_description or "",
                a.notes or "",
                a.charge_type or "",
                total,
                a.assigned_at.strftime("%Y-%m-%d %H:%M"),
            )

        archived_table.clear()
        for a in services.get_archived_storage_assignments():
            unit = services.get_storage_unit_by_id(a.unit_id)
            unit_label = unit.unit_number if unit else str(a.unit_id)
            name = a.assigned_to_name or ""
            total = f"${a.charge_total:.2f}" if a.charge_total is not None else ""
            archived_at = (
                a.archived_at.strftime("%Y-%m-%d %H:%M") if a.archived_at else ""
            )
            archived_table.add_row(
                str(a.id),
                unit_label,
                name,
                a.item_description or "",
                a.charge_type or "",
                total,
                archived_at,
            )

    def open_storage_assign_modal(self):
        """
        Opens the StorageAssignModal. The modal includes a unit selector dropdown
        so staff can choose which unit to assign without a separate picker step.
        """
        units = services.get_all_storage_units()
        if not units:
            self.app.notify(
                "No storage units exist. Create units in Settings > Storage Units first.",
                severity="warning",
            )
            return
        self.app.push_screen(
            StorageAssignModal(units=units),
            self._after_storage_assign,
        )

    def _after_storage_assign(self, result: bool):
        if result:
            self.load_storage_assignments()

    def open_storage_view_modal(self):
        """Opens the read-only view modal for the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        self.app.push_screen(
            StorageViewModal(assignment_id=self.selected_storage_assignment_id)
        )

    def open_storage_edit_modal(self):
        """Opens the edit modal for the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        assignment = services.get_storage_assignment_by_id(
            self.selected_storage_assignment_id
        )
        if not assignment:
            self.app.notify("Assignment not found.", severity="error")
            return
        units = services.get_all_storage_units()
        self.app.push_screen(
            StorageEditModal(assignment=assignment, units=units),
            self._after_storage_edit,
        )

    def _after_storage_edit(self, result: bool):
        if result:
            self.load_storage_assignments()

    def archive_storage_assignment(self):
        """Archives the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        ok = services.archive_storage_assignment(self.selected_storage_assignment_id)
        if ok:
            self.app.notify("Storage assignment archived.")
            self.selected_storage_assignment_id = None
            self.query_one("#btn_storage_view").disabled = True
            self.query_one("#btn_storage_edit").disabled = True
            self.query_one("#btn_storage_archive").disabled = True
        else:
            self.app.notify(
                "Could not archive: already archived or not found.", severity="error"
            )
        self.load_storage_assignments()

    # --- Inventory Cart ---

    def _load_inv_available_table(self):
        """Populates the available inventory items table in the Purchases tab."""
        try:
            table = self.query_one("#inv_available_table", DataTable)
        except Exception:
            return
        table.clear()
        for item in services.get_all_inventory_items():
            table.add_row(
                str(item.id), item.name, item.description or "", f"${item.price:.2f}"
            )

    def _rebuild_cart_table(self):
        """
        Clears and rebuilds the cart DataTable from _cart, then auto-fills
        pos_amount with the running total and pos_description with item names.
        """
        try:
            table = self.query_one("#inv_cart_table", DataTable)
            total_lbl = self.query_one("#inv_cart_total_lbl")
        except Exception:
            return

        table.clear()
        total = 0.0
        for entry in self._cart:
            subtotal = entry["qty"] * entry["unit_price"]
            total += subtotal
            table.add_row(
                entry["name"],
                str(entry["qty"]),
                f"${entry['unit_price']:.2f}",
                f"${subtotal:.2f}",
                key=str(entry["id"]),
            )

        total_lbl.update(f"Cart Total: ${total:.2f}")

        # Auto-fill the amount and description fields from cart contents
        try:
            self.query_one("#pos_amount", Input).value = f"{total:.2f}" if total else ""
            if self._cart:
                desc_parts = [
                    f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
                    for e in self._cart
                ]
                self.query_one("#pos_description", Input).value = ", ".join(desc_parts)
            else:
                self.query_one("#pos_description", Input).value = ""
        except Exception:
            pass

    def add_to_cart(self):
        """Adds the selected available item to the cart, merging qty if already present."""
        if not self._inv_selected_item:
            self.app.notify(
                "Click an item in the table to select it first.", severity="warning"
            )
            return
        try:
            qty = float(self.query_one("#inv_qty", Input).value or "1")
            if qty <= 0:
                self.app.notify("Quantity must be greater than zero.", severity="error")
                return
        except ValueError:
            qty = 1.0

        # Merge with existing cart entry for the same item
        for entry in self._cart:
            if entry["id"] == self._inv_selected_item["id"]:
                entry["qty"] += qty
                self._rebuild_cart_table()
                return

        self._cart.append(
            {
                "id": self._inv_selected_item["id"],
                "name": self._inv_selected_item["name"],
                "qty": qty,
                "unit_price": self._inv_selected_item["price"],
            }
        )
        self._rebuild_cart_table()

    def remove_from_cart(self):
        """Removes the selected cart row by item ID."""
        if self._inv_selected_cart_item_id is None:
            self.app.notify("Select a cart row first.", severity="warning")
            return
        self._cart = [
            e for e in self._cart if e["id"] != self._inv_selected_cart_item_id
        ]
        self._inv_selected_cart_item_id = None
        try:
            self.query_one("#btn_remove_from_cart").disabled = True
        except Exception:
            pass
        self._rebuild_cart_table()

    def clear_cart(self):
        """Empties the cart and resets all cart-related state."""
        self._cart = []
        self._inv_selected_cart_item_id = None
        try:
            self.query_one("#btn_remove_from_cart").disabled = True
        except Exception:
            pass
        self._rebuild_cart_table()

    def add_manual_to_cart(self):
        """Adds a custom (manual) line item to the cart from the POS form fields."""
        try:
            desc = self.query_one("#pos_manual_desc", Input).value.strip()
            price_str = self.query_one("#pos_manual_price", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not desc:
            self.app.notify("Please enter an item name/description.", severity="error")
            return
        try:
            price = float(price_str)
            if price <= 0:
                self.app.notify("Price must be greater than zero.", severity="error")
                return
        except (ValueError, TypeError):
            self.app.notify("Please enter a valid price.", severity="error")
            return

        self._manual_entry_counter += 1
        self._cart.append(
            {
                "id": f"manual_{self._manual_entry_counter}",
                "name": desc,
                "qty": 1,
                "unit_price": price,
            }
        )
        self._rebuild_cart_table()

        # Clear the manual entry fields after adding
        self.query_one("#pos_manual_desc", Input).value = ""
        self.query_one("#pos_manual_price", Input).value = ""
