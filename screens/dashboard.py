import time
from functools import partial

from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from core import exporters, models, services, square_service
from core.security import verify_password
from screens.modals import (
    CommunityContactsReportModal,
    ConfirmSignOutScreen,
    FeedbackViewModal,
    MemberActionModal,
    PeriodTractionReportModal,
    PeriodTransactionReportModal,
    PostActionCountdownModal,
    ProductSalesReportModal,
    SelectVisitTypeModal,
)
from screens.directory_select import DirectorySelectScreen
from screens.edit_profile import ChangePasswordScreen, EditProfileScreen
from screens.mixins import MembersMixin, POSMixin, StorageMixin
from screens.registration import RegisterScreen
from screens.settings_screen import SettingsScreen


class Dashboard(Screen, POSMixin, MembersMixin, StorageMixin):
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
            "id": "all_txns_table",
            "columns": [
                ("ID", 6),
                ("Date", 18),
                ("Customer", 20),
                ("Amount", 10),
                ("Type", 12),
                ("Description", 26),
                ("Status", 12),
                ("Via", 12),
                ("Processed By", 16),
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

    def action_open_website(self) -> None:
        """Opens the Spiritual Machines project website in the default browser."""
        import webbrowser

        webbrowser.open("https://spiritualmachines.ca")

    def action_open_manual(self) -> None:
        """Opens the Nucleus user manual on GitHub in the default browser."""
        import webbrowser

        webbrowser.open(
            "https://github.com/SpiritualMachines/nucleus/blob/main/USER_MANUAL.md"
        )

    def action_open_changelog(self) -> None:
        """Opens the Nucleus changelog on GitHub in the default browser."""
        import webbrowser

        webbrowser.open(
            "https://github.com/SpiritualMachines/nucleus/blob/main/CHANGELOG.md"
        )

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

        with Horizontal(id="top_bar"):
            yield Static(
                "[@click=screen.open_website]A Spiritual Machines Project[/]"
                "    |    "
                "[@click=screen.open_manual]View User Manual[/]"
                "    |    "
                "[@click=screen.open_changelog]View Change Log[/]"
                "    (Link May Open Under App)",
                id="link_bar",
                markup=True,
            )
            yield Static(f"Auto-logout: {self.AUTO_LOGOUT_SECONDS}s", id="logout_timer")

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
                with TabPane("Transactions"):
                    yield from self._compose_transactions_tab()

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

        yield Footer()

    def _compose_reports_tab(self) -> ComposeResult:
        """Yields widgets for the Reports tab."""
        with VerticalScroll(id="reports-tab-container"):
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
            yield Button(
                "Export Products / Services Sales Report",
                id="btn_product_sales_report",
            )

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
            "btn_product_sales_report": lambda: self.app.push_screen(
                ProductSalesReportModal()
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
            "btn_refresh_all_txns": self._load_all_transactions,
            "btn_check_txn_status": self.check_pos_terminal_status,
            "btn_issue_refund_txn": self._handle_issue_refund,
            "btn_edit_txn_details": self._handle_edit_txn_details,
            "btn_edit_txn_allocation": self._handle_edit_txn_allocation,
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
            self._load_all_transactions()
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

        elif event.data_table.id == "all_txns_table":
            row_data = event.data_table.get_row(event.row_key)
            id_str = str(row_data[0])
            if id_str.startswith("T"):
                # SquareTransaction row -- all actions are available
                self.selected_pos_txn_id = int(id_str[1:])
                via = str(row_data[7])
                self.query_one("#btn_check_txn_status").disabled = via != "Square"
                already_refunded = str(row_data[6]).strip().lower() == "refunded"
                self.query_one("#btn_issue_refund_txn").disabled = already_refunded
                self.query_one("#btn_edit_txn_details").disabled = False
                self.query_one("#btn_edit_txn_allocation").disabled = False
            else:
                # Daypass or membership row -- Square-specific actions not applicable
                self.selected_pos_txn_id = None
                self.query_one("#btn_check_txn_status").disabled = True
                self.query_one("#btn_issue_refund_txn").disabled = True
                self.query_one("#btn_edit_txn_details").disabled = True
                self.query_one("#btn_edit_txn_allocation").disabled = True
            self.app.notify(f"Selected transaction {id_str}")

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
