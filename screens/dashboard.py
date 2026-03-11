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
    TabbedContent,
    TabPane,
    TextArea,
)

from core import exporters, models, services, square_service
from core.config import settings
from core.security import verify_password
from screens.dashboard_modals import (
    AddDayPassModal,
    AddMembershipModal,
    CommunityContactsReportModal,
    ConfirmSignOutScreen,
    DayPassHistoryModal,
    FeedbackViewModal,
    ManageMembershipsModal,
    MemberActionModal,
    PeriodTractionReportModal,
    PostActionCountdownModal,
    SelectVisitTypeModal,
    TransactionModal,
    VISIT_TYPES,
)
from screens.directory_select import DirectorySelectScreen
from screens.edit_profile import ChangePasswordScreen, EditProfileScreen
from screens.registration import RegisterScreen


class Dashboard(Screen):
    # CSS to fix layout issues in Staff Tools and ensure visibility
    CSS = """
    .management-section {
        height: auto;
        margin-bottom: 2; /* Explicit margin */
        border-bottom: solid $secondary;
        padding-bottom: 1;
    }

    .pending-section {
        height: 1fr; /* Takes remaining space */
        min-height: 20;
    }

    /* FIX: Make table fill the space so buttons aren't stranded */
    #pending_table {
        height: 1fr;
        border: tall $primary;
    }

    /* FIX: Remove dock bottom so buttons flow naturally after the table */
    .pending-buttons {
        height: auto;
        margin-top: 1;
    }

    #logout_timer {
        width: 100%;
        text-align: right;
        background: $surface;
        color: $text-muted;
        padding-right: 2;
    }

    #logout_timer.urgent {
        color: $error;
        text-style: bold;
    }

    /* --- Database Tab Specifics --- */
    .query-presets {
        height: auto;
        max-height: 15;
        border: solid $secondary;
        background: $boost;
        padding: 1;
        margin-bottom: 1;
        overflow-y: auto;
    }

    #sql_results {
        height: 1fr; /* Table takes remaining space and scrolls internally */
        min-height: 10;
        border: tall $primary;
    }

    .export-section {
        height: auto;
        margin-top: 1;
        padding-top: 1;
        border-top: solid $secondary;
    }

    /* --- Purchases Tab --- */
    .purchase-section {
        height: auto;
        margin-bottom: 2;
        border: solid $secondary;
        padding: 1;
        background: $boost;
    }

    .search-row {
        height: auto;
        margin-bottom: 1;
    }

    #user_search_table, #my_mem_table, #my_daypass_table, #my_cons_table {
        height: 10; /* Fixed small height for search results */
        border: solid $secondary;
        margin-bottom: 1;
    }

    /* --- Staff Tools Search --- */
    #staff_user_search_table {
        height: 10;
        border: solid $secondary;
        margin-bottom: 1;
    }

    /* --- Settings Tab --- */
    #setting_ascii_logo {
        height: 13;
        border: solid $secondary;
        margin-bottom: 1;
    }
    """

    AUTO_LOGOUT_SECONDS = 600  # 10 Minutes

    # Track selected user for unified Existing User Transactions section
    selected_user_acct = None
    # Track selected POS transaction row for status checks
    selected_pos_txn_id = None
    # Track active device pairing code ID for polling
    _pos_pairing_code_id = None

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

        # Security Timer Label
        yield Label(f"Auto-logout: {self.AUTO_LOGOUT_SECONDS}s", id="logout_timer")

        yield Label("", id="pending_alert", classes="hidden")

        with TabbedContent():
            # Tab 1: My Profile
            with TabPane("My Profile"):
                # Safe role access (handles both Enum and String cases)
                role_val = (
                    user.role.value if hasattr(user.role, "value") else str(user.role)
                )
                role_name = (
                    user.role.name if hasattr(user.role, "name") else str(user.role)
                )

                yield Label(
                    f"Welcome, {role_val.title()} {user.first_name}!",
                    classes="title",
                    id="welcome_lbl",
                )
                yield Label(f"Account Type: {role_name}", id="lbl_role")
                yield Label(f"Account #: {user.account_number}", id="lbl_acct")
                yield Label("Credit Balance: $0.00", id="lbl_balance")

                yield Button("Edit My Information", id="edit_profile_btn")
                yield Button("Change Password", id="change_pwd_btn")

                yield Button(
                    "Sign In to Makerspace", id="signin_btn"
                )  # Label updated on mount by update_signin_button
                yield Button("Logout", id="logout_btn")

                yield Label("My Preferences", classes="subtitle")

                yield Label("Preferred Visit Type (leave blank to always be asked):")
                yield Select(
                    [("No preference (always ask)", "")]
                    + [(vt, vt) for vt in VISIT_TYPES],
                    id="pref_visit_type",
                    value="",
                )

                yield Button("Save Preferences", id="btn_save_prefs")

            # Tab 2: Staff Actions (Available to Staff and Admin)
            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                with TabPane("Staff Tools"):
                    with Vertical(classes="management-section"):
                        yield Label("User Management", classes="title")
                        yield Button(
                            "Register New Member (In-Person)", id="btn_staff_reg"
                        )

                    # --- NEW SECTION: Quick User Search ---
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
                    # --------------------------------------

                    with Vertical(classes="pending-section"):
                        yield Label("Pending Approvals", classes="title")
                        yield DataTable(id="pending_table")

                        # Stacked buttons
                        with Vertical(classes="pending-buttons"):
                            yield Button(
                                "Approve Selected Account",
                                variant="success",
                                id="approve_btn",
                            )
                            yield Button("Refresh List", id="refresh_pending")

            # --- PURCHASES TAB (Visible to Everyone, but different content) ---
            with TabPane("Purchases"):
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

                            yield Label("Amount ($):")
                            yield Input(
                                placeholder="0.00",
                                id="pos_amount",
                                type="number",
                            )

                            yield Label("Customer Name:")
                            yield Input(
                                placeholder="First and Last Name",
                                id="pos_customer_name",
                            )

                            yield Label("Customer Email (optional):")
                            yield Input(
                                placeholder="customer@example.com",
                                id="pos_customer_email",
                            )

                            yield Label("Customer Phone (optional):")
                            yield Input(
                                placeholder="Phone number",
                                id="pos_customer_phone",
                            )

                            yield Label("Description:")
                            yield Input(
                                placeholder="What is this transaction for?",
                                id="pos_description",
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

                            yield Label("Recent Transactions:", classes="subtitle")
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

                        # Subsection 1: Existing User Transactions (consolidated)
                        with Vertical(classes="purchase-section"):
                            yield Label(
                                "Existing User Transactions", classes="subtitle"
                            )
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
                            yield Label(
                                "Actions for Selected User:", classes="subtitle"
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

                    # === REGULAR USER VIEW ===
                    else:
                        # Subsection 1: My Memberships
                        with Vertical(classes="purchase-section"):
                            yield Label("My Memberships", classes="subtitle")
                            yield DataTable(id="my_mem_table")

                        # Subsection 2: My Day Passes
                        with Vertical(classes="purchase-section"):
                            yield Label("My Day Passes", classes="subtitle")
                            yield DataTable(id="my_daypass_table")

                        # Subsection 3: My Consumables
                        with Vertical(classes="purchase-section"):
                            yield Label(f"My {currency} Ledger", classes="subtitle")
                            yield Label(
                                f"{currency} Balance: $0.00", id="my_balance_lbl"
                            )
                            yield DataTable(id="my_cons_table")

            # Tab 4: Reports (Staff/Admin)
            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                with TabPane("Reports"):  # Renamed from "Membership Reports"
                    yield Label("Membership Reports", classes="title")
                    yield Label("(Click any row to Manage User)", classes="subtitle")

                    with Horizontal(classes="filter-row"):
                        yield Checkbox("Admin", value=True, id="chk_admin")
                        yield Checkbox("Staff", value=True, id="chk_staff")
                        yield Checkbox("Member (Active)", value=True, id="chk_member")
                        yield Checkbox(
                            "Community (Inactive)", value=False, id="chk_community"
                        )
                        yield Checkbox("Signed In", value=False, id="chk_signed_in")

                    yield Button("Refresh Report", id="load_members")
                    yield DataTable(id="members_table")

                    yield Label("Export Options:", classes="subtitle")
                    yield Button("Export CSV", id="btn_export_members_csv")
                    yield Button("Export PDF", id="btn_export_members_pdf")

                    yield Label("Admin and Statistics Reports:", classes="subtitle")
                    yield Button(
                        "Export Period Traction Report",
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

            # Tab 5: Database (Available to ADMIN ONLY)
            if user.role == models.UserRole.ADMIN:
                with TabPane("Database"):
                    sql_console_enabled = (
                        services.get_setting("sql_console_enabled", "true").lower()
                        == "true"
                    )

                    if not sql_console_enabled:
                        yield Label(
                            "SQL Console is disabled by the administrator.",
                            classes="subtitle",
                        )
                    else:
                        # --- LOCKED STATE VIEW ---
                        with Center(id="db_lock_wrapper"):
                            with Vertical(
                                id="db_locked_view", classes="login-container"
                            ):
                                yield Label("SECURITY WARNING", classes="title error")
                                yield Label(
                                    "You are accessing Raw SQL Controls.",
                                    classes="subtitle",
                                )
                                yield Label(
                                    "Bad commands can permanently DELETE or CORRUPT data.",
                                    classes="error",
                                )
                                yield Label(
                                    "Proceed with extreme caution.", classes="subtitle"
                                )

                                yield Input(
                                    placeholder="Confirm Admin Password",
                                    password=True,
                                    id="db_pass_input",
                                )

                                yield Button(
                                    "Unlock", variant="error", id="btn_verify_unlock"
                                )

                        # --- UNLOCKED STATE VIEW (Hidden Initially) ---
                        with Vertical(id="db_unlocked_view", classes="hidden"):
                            yield Label(
                                "Raw SQL Execution (Danger Zone)", classes="title"
                            )

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
                            yield Button(
                                "Execute SQL", variant="error", id="exec_sql_btn"
                            )

                            yield Label("", id="sql_status")

                            yield DataTable(id="sql_results")

                            with Vertical(classes="export-section"):
                                yield Label("Export Options:", classes="subtitle")
                                yield Button(
                                    "Export Results CSV", id="btn_export_sql_csv"
                                )
                                yield Button(
                                    "Export Results PDF", id="btn_export_sql_pdf"
                                )

            # Tab 6: Settings (Admin only)
            if user.role == models.UserRole.ADMIN:
                with TabPane("Settings"):
                    with TabbedContent():
                        # --- General ---
                        with TabPane("General"):
                            with VerticalScroll():
                                yield Label("General Settings", classes="title")

                                yield Label("Hackspace Name:")
                                yield Input(
                                    services.get_setting(
                                        "hackspace_name", settings.HACKSPACE_NAME
                                    ),
                                    id="setting_hackspace_name",
                                )

                                yield Label(
                                    "Tag Name (short label used on buttons, e.g. Makerspace):"
                                )
                                yield Input(
                                    services.get_setting("tag_name", settings.TAG_NAME),
                                    id="setting_tag_name",
                                )

                                yield Label("App Name:")
                                yield Input(
                                    services.get_setting("app_name", settings.APP_NAME),
                                    id="setting_app_name",
                                )

                                yield Label("ASCII Logo:")
                                yield TextArea(id="setting_ascii_logo")

                                yield Label("Auto-Logout Timeout (minutes):")
                                yield Input(
                                    services.get_setting(
                                        "logout_timeout_minutes", "10"
                                    ),
                                    id="setting_logout_minutes",
                                    type="integer",
                                )

                                yield Button(
                                    "Save General Settings",
                                    variant="success",
                                    id="btn_save_general",
                                )

                        # --- Operations ---
                        with TabPane("Operations"):
                            with VerticalScroll():
                                yield Label("Space Operations", classes="title")

                                yield Label(
                                    "Membership Grace Period (days after expiry before role downgrade, 0 = immediate):"
                                )
                                yield Input(
                                    services.get_setting(
                                        "membership_grace_period_days", "0"
                                    ),
                                    id="setting_grace_period",
                                    type="integer",
                                )

                                yield Label("Day Pass Cost (currency units, 0 = free):")
                                yield Input(
                                    services.get_setting("day_pass_cost_credits", "0"),
                                    id="setting_daypass_cost",
                                    type="integer",
                                )

                                yield Label("Max Concurrent Sign-Ins (0 = unlimited):")
                                yield Input(
                                    services.get_setting("max_concurrent_signins", "0"),
                                    id="setting_max_signins",
                                    type="integer",
                                )

                                yield Label(
                                    "Backup Retention (days to keep, 0 = keep all):"
                                )
                                yield Input(
                                    services.get_setting("backup_retention_days", "30"),
                                    id="setting_backup_retention",
                                    type="integer",
                                )

                                yield Button(
                                    "Save Operations Settings",
                                    variant="success",
                                    id="btn_save_operations",
                                )

                        # --- Branding ---
                        with TabPane("Branding"):
                            with VerticalScroll():
                                yield Label("Branding and Reporting", classes="title")

                                yield Label(
                                    "Currency Name (what your space calls its internal currency, e.g. Credits, Hackerbucks):"
                                )
                                yield Input(
                                    services.get_setting(
                                        "app_currency_name", "Credits"
                                    ),
                                    id="setting_currency_name",
                                )

                                yield Label("Default Export Format:")
                                yield Select(
                                    [("CSV", "csv"), ("PDF", "pdf")],
                                    id="setting_default_export",
                                    value=services.get_setting(
                                        "default_export_format", "csv"
                                    ),
                                )

                                yield Label(
                                    "PDF Report Header Text (shown below title on all PDF exports):"
                                )
                                yield Input(
                                    services.get_setting("report_header_text", ""),
                                    id="setting_report_header",
                                )

                                yield Label("Staff Reply-To Email Address (optional):")
                                yield Input(
                                    services.get_setting("staff_email", ""),
                                    id="setting_staff_email",
                                )

                                yield Button(
                                    "Save Branding Settings",
                                    variant="success",
                                    id="btn_save_branding",
                                )

                        # --- Security ---
                        with TabPane("Security"):
                            with VerticalScroll():
                                yield Label("Security Settings", classes="title")

                                yield Label("Minimum Password Length:")
                                yield Input(
                                    services.get_setting("min_password_length", "8"),
                                    id="setting_min_pwd_len",
                                    type="integer",
                                )

                                yield Label(
                                    "Max Login Attempts Before Lockout (0 = unlimited, lockout lasts 30 minutes):"
                                )
                                yield Input(
                                    services.get_setting("login_attempt_limit", "0"),
                                    id="setting_login_limit",
                                    type="integer",
                                )

                                yield Checkbox(
                                    "SQL Console Enabled (changes take effect on next login)",
                                    id="setting_sql_console",
                                    value=services.get_setting(
                                        "sql_console_enabled", "true"
                                    ).lower()
                                    == "true",
                                )

                                yield Button(
                                    "Save Security Settings",
                                    variant="success",
                                    id="btn_save_security",
                                )

                        # --- Point of Sale ---
                        with TabPane("Point of Sale"):
                            with VerticalScroll():
                                yield Label("Point of Sale Settings", classes="title")
                                yield Label(
                                    "Configure Square Terminal integration for processing card payments."
                                )

                                pos_cfg = square_service.get_pos_config()

                                yield Checkbox(
                                    "Enable Square Terminal",
                                    id="setting_square_enabled",
                                    value=pos_cfg.square_enabled,
                                )

                                yield Label("Square Environment:")
                                yield Select(
                                    [
                                        ("Sandbox (Testing)", "sandbox"),
                                        ("Production (Live)", "production"),
                                    ],
                                    id="setting_square_env",
                                    value=pos_cfg.square_environment,
                                )

                                yield Label("Sandbox Access Token:")
                                yield Input(
                                    placeholder=(
                                        "Sandbox token configured - paste to replace"
                                        if square_service.pos_sandbox_token_is_configured()
                                        else "Paste Square sandbox token here..."
                                    ),
                                    id="setting_square_token_sandbox",
                                )
                                yield Button(
                                    "Save Sandbox Token",
                                    id="btn_save_square_token_sandbox",
                                    variant="success",
                                )

                                yield Label("Production Access Token:")
                                yield Input(
                                    placeholder=(
                                        "Production token configured - paste to replace"
                                        if square_service.pos_production_token_is_configured()
                                        else "Paste Square production token here..."
                                    ),
                                    id="setting_square_token_production",
                                )
                                yield Button(
                                    "Save Production Token",
                                    id="btn_save_square_token_production",
                                    variant="success",
                                )

                                yield Label("Square Location ID:")
                                yield Input(
                                    pos_cfg.square_location_id,
                                    placeholder="Your Square location ID",
                                    id="setting_square_location_id",
                                )

                                yield Label("Square Device ID:")
                                yield Input(
                                    pos_cfg.square_device_id,
                                    placeholder="Terminal device ID from Square Dashboard",
                                    id="setting_square_device_id",
                                )

                                yield Label("Currency:")
                                yield Select(
                                    [
                                        ("CAD - Canadian Dollar", "CAD"),
                                        ("USD - US Dollar", "USD"),
                                        ("AUD - Australian Dollar", "AUD"),
                                        ("GBP - British Pound", "GBP"),
                                        ("EUR - Euro", "EUR"),
                                        ("JPY - Japanese Yen", "JPY"),
                                        ("CHF - Swiss Franc", "CHF"),
                                        ("NZD - New Zealand Dollar", "NZD"),
                                        ("SGD - Singapore Dollar", "SGD"),
                                        ("HKD - Hong Kong Dollar", "HKD"),
                                        ("SEK - Swedish Krona", "SEK"),
                                        ("NOK - Norwegian Krone", "NOK"),
                                        ("DKK - Danish Krone", "DKK"),
                                        ("CNY - Chinese Yuan", "CNY"),
                                        ("MXN - Mexican Peso", "MXN"),
                                        ("BRL - Brazilian Real", "BRL"),
                                        ("INR - Indian Rupee", "INR"),
                                        ("ZAR - South African Rand", "ZAR"),
                                        ("AED - UAE Dirham", "AED"),
                                        ("SAR - Saudi Riyal", "SAR"),
                                        ("QAR - Qatari Riyal", "QAR"),
                                        ("KWD - Kuwaiti Dinar", "KWD"),
                                        ("BHD - Bahraini Dinar", "BHD"),
                                        ("OMR - Omani Rial", "OMR"),
                                        ("JOD - Jordanian Dinar", "JOD"),
                                        ("ILS - Israeli New Shekel", "ILS"),
                                        ("TRY - Turkish Lira", "TRY"),
                                        ("PLN - Polish Zloty", "PLN"),
                                        ("CZK - Czech Koruna", "CZK"),
                                        ("HUF - Hungarian Forint", "HUF"),
                                        ("RON - Romanian Leu", "RON"),
                                        ("THB - Thai Baht", "THB"),
                                        ("MYR - Malaysian Ringgit", "MYR"),
                                        ("PHP - Philippine Peso", "PHP"),
                                        ("IDR - Indonesian Rupiah", "IDR"),
                                        ("KRW - South Korean Won", "KRW"),
                                        ("TWD - Taiwan Dollar", "TWD"),
                                        ("VND - Vietnamese Dong", "VND"),
                                        ("PKR - Pakistani Rupee", "PKR"),
                                        ("BDT - Bangladeshi Taka", "BDT"),
                                        ("LKR - Sri Lankan Rupee", "LKR"),
                                        ("NGN - Nigerian Naira", "NGN"),
                                        ("KES - Kenyan Shilling", "KES"),
                                        ("GHS - Ghanaian Cedi", "GHS"),
                                        ("EGP - Egyptian Pound", "EGP"),
                                        ("MAD - Moroccan Dirham", "MAD"),
                                        ("CLP - Chilean Peso", "CLP"),
                                        ("COP - Colombian Peso", "COP"),
                                        ("PEN - Peruvian Sol", "PEN"),
                                        ("ARS - Argentine Peso", "ARS"),
                                    ],
                                    id="setting_square_currency",
                                    value=pos_cfg.square_currency or "CAD",
                                )

                                yield Button(
                                    "Save POS Settings",
                                    variant="success",
                                    id="btn_save_pos_settings",
                                )

                                yield Label("Terminal Pairing", classes="subtitle")
                                yield Label(
                                    "If your terminal is not receiving checkouts,"
                                    " it needs to be paired for Terminal API use."
                                )
                                yield Label(
                                    "Click 'Pair Terminal', then on the terminal:"
                                    " tap the three-dot menu, go to Settings > Device,"
                                )
                                yield Label(
                                    "tap 'Pair for Terminal API', and enter the code"
                                    " shown below. Then click 'Check Pairing Status'."
                                )
                                with Horizontal(classes="filter-row"):
                                    yield Button(
                                        "Pair Terminal",
                                        variant="primary",
                                        id="btn_pair_terminal",
                                    )
                                    yield Button(
                                        "Check Pairing Status",
                                        id="btn_check_pairing",
                                        disabled=True,
                                    )
                                yield Label("", id="lbl_pairing_code")

                        # --- Email and Notifications ---
                        with TabPane("Email and Notifications"):
                            with VerticalScroll():
                                yield Label("Email and Notifications", classes="title")

                                # The API key input is always visible. The placeholder
                                # changes to indicate whether a key is already stored.
                                # Pasting a new value and clicking Save Key overwrites
                                # whatever was there before — the raw value is never
                                # pre-filled or displayed.
                                yield Label("Resend API Key:")
                                yield Input(
                                    placeholder=(
                                        "Key configured - paste new key to replace"
                                        if services.sensitive_setting_is_configured(
                                            "resend_api_key"
                                        )
                                        else "Paste Resend API key here..."
                                    ),
                                    id="setting_resend_api_key_input",
                                )
                                yield Button(
                                    "Save Key",
                                    id="btn_save_api_key",
                                    variant="success",
                                )

                                yield Label("From Email Address:")
                                yield Input(
                                    services.get_setting(
                                        "report_from_email", "onboarding@resend.dev"
                                    ),
                                    id="setting_from_email",
                                )

                                yield Label("Send Daily Report To (email):")
                                yield Input(
                                    services.get_setting("report_to_email", ""),
                                    id="setting_to_email",
                                )

                                yield Label(
                                    "Daily Report Send Time (24-hour HH:MM, e.g. 07:00):"
                                )
                                yield Input(
                                    services.get_setting("report_send_time", "07:00"),
                                    id="setting_report_send_time",
                                )

                                yield Checkbox(
                                    "Enable Daily Email Reports",
                                    id="setting_email_reports_enabled",
                                    value=services.get_setting(
                                        "email_reports_enabled", "false"
                                    ).lower()
                                    == "true",
                                )

                                with Horizontal():
                                    yield Button(
                                        "Save Email Settings",
                                        variant="success",
                                        id="btn_save_email",
                                    )
                                    yield Button(
                                        "Send Test Email",
                                        variant="primary",
                                        id="btn_test_email",
                                    )

            # Tab 7: Feedback
            with TabPane("Feedback"):
                yield Label("Submit Feedback / Bug Reports", classes="title")

                with Horizontal(classes="agreement-row"):
                    yield Checkbox("General Feedback", id="chk_fb_general")
                    yield Checkbox("Feature Request", id="chk_fb_feature")
                    yield Checkbox("Bug Report", id="chk_fb_bug")
                    yield Label("   ")
                    yield Checkbox("URGENT", id="chk_fb_urgent")

                yield Input(placeholder="Type your comment here...", id="fb_comment")
                yield Button(
                    "Submit Feedback", variant="primary", id="btn_submit_feedback"
                )

                # --- VISIBILITY RESTRICTION: Only Staff/Admin see the table and exports ---
                if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                    yield Label("Recent Submissions", classes="subtitle")
                    yield DataTable(id="feedback_table")
                    yield Button("Refresh List", id="btn_refresh_feedback")

                    yield Label("Export Options:", classes="subtitle")
                    yield Button("Export CSV", id="btn_export_fb_csv")
                    yield Button("Export PDF", id="btn_export_fb_pdf")

        yield Footer()

    def on_mount(self):
        user = self.app.current_user
        currency = services.get_setting("app_currency_name", "Credits")
        self.update_signin_button()

        # Initialize Security Timer — read timeout from DB, fall back to class default
        try:
            self.AUTO_LOGOUT_SECONDS = (
                int(services.get_setting("logout_timeout_minutes", "10")) * 60
            )
        except ValueError:
            pass  # Keep the class-level default if the stored value is invalid
        self.last_activity = time.time()
        self.set_interval(1.0, self.update_security_timer)

        # Initialize Feedback Table ONLY if visible
        if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
            fb_table = self.query_one("#feedback_table", DataTable)
            if fb_table:
                # UPDATED: Replaced add_columns with individual add_column calls to set explicit widths
                fb_table.add_column("ID", width=4)
                fb_table.add_column("Date", width=18)
                fb_table.add_column("Name", width=20)
                fb_table.add_column("Urgent", width=8)
                fb_table.add_column("Comment Preview", width=45)
                fb_table.add_column("Response", width=45)

                fb_table.cursor_type = "row"
            self.load_feedback()

        # Permissions check for Staff/Admin tables
        if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
            # Initialize Tables
            pending_table = self.query_one("#pending_table", DataTable)
            if pending_table:
                pending_table.add_columns("Acct #", "Name", "Email", "Date Joined")
                pending_table.cursor_type = "row"

            members_table = self.query_one("#members_table", DataTable)
            if members_table:
                members_table.add_columns("Acct #", "Name", "Role", "Email")
                members_table.cursor_type = "row"

            # Initialize Unified User Search Table
            user_search_table = self.query_one("#user_search_table", DataTable)
            if user_search_table:
                user_search_table.add_columns("Acct #", "Name", "Email")
                user_search_table.cursor_type = "row"

            # Initialize Staff Tool Search Table
            st_table = self.query_one("#staff_user_search_table", DataTable)
            if st_table:
                st_table.add_columns("Acct #", "Name", "Email")
                st_table.cursor_type = "row"

            # Initialize POS transactions table
            pos_table = self.query_one("#pos_txns_table", DataTable)
            if pos_table:
                pos_table.add_column("ID", width=5)
                pos_table.add_column("Date", width=18)
                pos_table.add_column("Customer", width=22)
                pos_table.add_column("Amount", width=10)
                pos_table.add_column("Description", width=28)
                pos_table.add_column("Status", width=12)
                pos_table.add_column("Via", width=8)
                pos_table.cursor_type = "row"
            self.load_pos_transactions()

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
            ):
                self.query_one(f"#{btn_id}").disabled = False
            self.app.notify(f"Selected: {row_data[1]}")

        elif event.data_table.id == "pos_txns_table":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_pos_txn_id = int(row_data[0])
            # Only enable status check for Square transactions (not local records)
            via = str(row_data[6])
            self.query_one("#btn_check_pos_status").disabled = via != "Square"
            self.app.notify(f"Selected transaction #{self.selected_pos_txn_id}")

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

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated):
        # TextArea.wrap_width reads scrollable_content_region.size, which is zero
        # while the pane is hidden. Deferring via call_after_refresh lets the layout
        # engine compute the real size before load_text wraps the content.
        self.call_after_refresh(self._load_ascii_logo_if_needed)

    def _load_ascii_logo_if_needed(self):
        results = self.query("#setting_ascii_logo")
        if not results:
            return
        logo_area = results.first(TextArea)
        if not logo_area.text:
            logo_area.load_text(services.get_setting("ascii_logo", settings.ASCII_LOGO))

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
        if event.button.id == "logout_btn":
            self.app.current_user = None
            self.app.pop_screen()
        elif event.button.id == "signin_btn":
            acct = self.app.current_user.account_number
            try:
                if services.is_user_signed_in(acct):
                    self.app.push_screen(
                        ConfirmSignOutScreen(), self.on_signout_confirm
                    )
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
        elif event.button.id == "change_pwd_btn":
            self.app.push_screen(ChangePasswordScreen())
        elif event.button.id == "edit_profile_btn":
            self.app.push_screen(EditProfileScreen(), self.refresh_profile)
        elif event.button.id == "btn_staff_reg":
            self.app.push_screen(RegisterScreen(staff_mode=True))
        elif event.button.id == "btn_save_prefs":
            self.save_user_preferences()

        elif event.button.id == "btn_save_general":
            self.save_settings_general()
        elif event.button.id == "btn_save_operations":
            self.save_settings_operations()
        elif event.button.id == "btn_save_branding":
            self.save_settings_branding()
        elif event.button.id == "btn_save_security":
            self.save_settings_security()
        elif event.button.id == "btn_save_api_key":
            self.save_api_key()
        elif event.button.id == "btn_save_email":
            self.save_settings_email()
        elif event.button.id == "btn_test_email":
            self.send_test_email()

        # --- FEEDBACK HANDLERS ---
        elif event.button.id == "btn_submit_feedback":
            self.submit_feedback_action()
        elif event.button.id == "btn_refresh_feedback":
            self.load_feedback()
        elif event.button.id == "btn_export_fb_csv":
            self.initiate_export(
                "#feedback_table", "feedback_report", "csv", full_feedback=True
            )
        elif event.button.id == "btn_export_fb_pdf":
            self.initiate_export(
                "#feedback_table", "feedback_report", "pdf", full_feedback=True
            )

        elif event.button.id == "refresh_pending":
            self.load_pending()
            self.update_pending_alert()
        elif event.button.id == "load_members":
            self.load_members()
        elif event.button.id == "approve_btn":
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

        # --- STAFF TOOL SEARCH ---
        elif event.button.id == "btn_staff_user_search":
            self.action_staff_user_search()

        # --- DATABASE LOCK HANDLERS ---
        elif event.button.id == "btn_verify_unlock":
            self.verify_database_unlock()

        # --- SQL PRESETS ---
        elif event.button.id == "sql_q1":
            self.query_one(
                "#sql_input"
            ).value = "SELECT first_name, last_name, allergies, health_concerns FROM user WHERE allergies != '' OR health_concerns != ''"
        elif event.button.id == "sql_q2":
            self.query_one(
                "#sql_input"
            ).value = "SELECT first_name, last_name, emergency_first_name, emergency_phone FROM user"
        elif event.button.id == "sql_q3":
            self.query_one(
                "#sql_input"
            ).value = "SELECT u.first_name, u.last_name, u.email FROM user u JOIN safetytraining s ON u.account_number = s.user_account_number WHERE s.orientation = 0"
        elif event.button.id == "sql_q4":
            self.query_one(
                "#sql_input"
            ).value = "SELECT role, COUNT(*) as count FROM user GROUP BY role"
        elif event.button.id == "sql_q5":
            self.query_one(
                "#sql_input"
            ).value = "SELECT u.first_name, u.last_name, s.sign_in_time, s.sign_out_time FROM spaceattendance s JOIN user u ON s.user_account_number = u.account_number WHERE s.sign_in_time BETWEEN '2025-01-01 00:00:00' AND '2025-12-31 23:59:59'"

        elif event.button.id == "exec_sql_btn":
            query = self.query_one("#sql_input").value
            self.run_raw_sql(query)

        # --- EXPORT HANDLERS ---
        elif event.button.id == "btn_export_members_csv":
            self.initiate_export("#members_table", "members_report", "csv")
        elif event.button.id == "btn_export_members_pdf":
            self.initiate_export("#members_table", "members_report", "pdf")
        elif event.button.id == "btn_export_sql_csv":
            self.initiate_export("#sql_results", "sql_query_result", "csv")
        elif event.button.id == "btn_export_sql_pdf":
            self.initiate_export("#sql_results", "sql_query_result", "pdf")
        elif event.button.id == "btn_period_traction_report":
            self.app.push_screen(PeriodTractionReportModal())
        elif event.button.id == "btn_community_contacts_report":
            self.app.push_screen(CommunityContactsReportModal())
        elif event.button.id == "btn_everything_people_csv":
            self.initiate_everything_people_csv()

        # --- UNIFIED USER SEARCH ---
        elif event.button.id == "btn_user_search":
            self.action_search_users()

        # --- MEMBERSHIP ACTIONS ---
        elif event.button.id == "btn_add_mem":
            if self.selected_user_acct:
                self.app.push_screen(
                    AddMembershipModal(self.selected_user_acct),
                    self._refresh_user_table,
                )
        elif event.button.id == "btn_edit_mem":
            if self.selected_user_acct:
                self.app.push_screen(ManageMembershipsModal(self.selected_user_acct))

        # --- DAY PASS ACTIONS ---
        elif event.button.id == "btn_add_daypass":
            if self.selected_user_acct:
                self.app.push_screen(
                    AddDayPassModal(self.selected_user_acct), self._refresh_user_table
                )
        elif event.button.id == "btn_view_daypass":
            if self.selected_user_acct:
                self.app.push_screen(DayPassHistoryModal(self.selected_user_acct))

        # --- CREDITS ACTIONS ---
        elif event.button.id == "btn_credit":
            if self.selected_user_acct:
                currency = services.get_setting("app_currency_name", "Credits")
                self.app.push_screen(
                    TransactionModal(self.selected_user_acct, "credit", currency),
                    self._refresh_user_table,
                )
        elif event.button.id == "btn_debit":
            if self.selected_user_acct:
                currency = services.get_setting("app_currency_name", "Credits")
                self.app.push_screen(
                    TransactionModal(self.selected_user_acct, "debit", currency),
                    self._refresh_user_table,
                )

        # --- POS / MANUAL TRANSACTION ACTIONS ---
        elif event.button.id == "btn_process_manual_txn":
            self.process_manual_transaction()
        elif event.button.id == "btn_record_cash_txn":
            self.record_cash_transaction()
        elif event.button.id == "btn_clear_pos_form":
            self.clear_pos_form()
        elif event.button.id == "btn_refresh_pos_txns":
            self.load_pos_transactions()
        elif event.button.id == "btn_check_pos_status":
            self.check_pos_terminal_status()

        # --- POS SETTINGS ACTIONS ---
        elif event.button.id == "btn_save_square_token_sandbox":
            self.save_square_token("sandbox")
        elif event.button.id == "btn_save_square_token_production":
            self.save_square_token("production")
        elif event.button.id == "btn_save_pos_settings":
            self.save_pos_settings()
        elif event.button.id == "btn_pair_terminal":
            self.pair_terminal()
        elif event.button.id == "btn_check_pairing":
            self.check_terminal_pairing()

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

    @staticmethod
    def _parse_non_neg_int(val: str, label: str) -> int:
        """Parses a non-negative integer or raises ValueError with a human-readable message."""
        try:
            n = int(val)
            if n < 0:
                raise ValueError()
            return n
        except ValueError:
            raise ValueError(f"{label} must be a whole number of zero or greater.")

    def save_settings_general(self):
        """Validates and persists General settings, applying changes live where possible."""
        try:
            hackspace_name = self.query_one("#setting_hackspace_name").value.strip()
            tag_name = self.query_one("#setting_tag_name").value.strip()
            app_name = self.query_one("#setting_app_name").value.strip()
            ascii_logo = self.query_one("#setting_ascii_logo", TextArea).text
            logout_minutes_str = self.query_one("#setting_logout_minutes").value.strip()

            if not hackspace_name:
                self.app.notify("Hackspace Name cannot be empty.", severity="error")
                return
            if not tag_name:
                self.app.notify("Tag Name cannot be empty.", severity="error")
                return
            try:
                logout_minutes = int(logout_minutes_str)
                if logout_minutes < 1:
                    raise ValueError()
            except ValueError:
                self.app.notify(
                    "Auto-Logout Timeout must be a positive whole number.",
                    severity="error",
                )
                return

            services.set_setting("hackspace_name", hackspace_name)
            services.set_setting("tag_name", tag_name)
            services.set_setting("app_name", app_name)
            services.set_setting("ascii_logo", ascii_logo)
            services.set_setting("logout_timeout_minutes", str(logout_minutes))

            self.app.title = hackspace_name
            self.AUTO_LOGOUT_SECONDS = logout_minutes * 60
            self.update_signin_button()
            self.reset_activity()
            self.app.notify("General settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    def save_settings_operations(self):
        """Validates and persists Space Operations settings."""
        try:
            grace_period = self._parse_non_neg_int(
                self.query_one("#setting_grace_period").value.strip(),
                "Membership Grace Period",
            )
            daypass_cost = self._parse_non_neg_int(
                self.query_one("#setting_daypass_cost").value.strip(), "Day Pass Cost"
            )
            max_signins = self._parse_non_neg_int(
                self.query_one("#setting_max_signins").value.strip(),
                "Max Concurrent Sign-Ins",
            )
            backup_retention = self._parse_non_neg_int(
                self.query_one("#setting_backup_retention").value.strip(),
                "Backup Retention",
            )

            services.set_setting("membership_grace_period_days", str(grace_period))
            services.set_setting("day_pass_cost_credits", str(daypass_cost))
            services.set_setting("max_concurrent_signins", str(max_signins))
            services.set_setting("backup_retention_days", str(backup_retention))
            self.app.notify("Operations settings saved.")
        except ValueError as e:
            self.app.notify(str(e), severity="error")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    def save_settings_branding(self):
        """Validates and persists Branding and Reporting settings."""
        try:
            currency_name = self.query_one("#setting_currency_name").value.strip()
            default_export = (
                self.query_one("#setting_default_export", Select).value or "csv"
            )
            report_header = self.query_one("#setting_report_header").value.strip()
            staff_email = self.query_one("#setting_staff_email").value.strip()

            if not currency_name:
                self.app.notify("Currency Name cannot be empty.", severity="error")
                return
            if default_export not in ("csv", "pdf"):
                self.app.notify(
                    "Default Export Format must be csv or pdf.", severity="error"
                )
                return
            if staff_email:
                try:
                    from email_validator import validate_email

                    validate_email(staff_email, check_deliverability=False)
                except Exception:
                    self.app.notify(
                        "Staff Email must be a valid email address or left blank.",
                        severity="error",
                    )
                    return

            services.set_setting("app_currency_name", currency_name)
            services.set_setting("default_export_format", default_export)
            services.set_setting("report_header_text", report_header)
            services.set_setting("staff_email", staff_email)
            self.app.notify("Branding settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    def save_settings_security(self):
        """Validates and persists Security settings."""
        try:
            min_pwd_len_str = self.query_one("#setting_min_pwd_len").value.strip()
            login_limit_str = self.query_one("#setting_login_limit").value.strip()
            sql_console_enabled = self.query_one("#setting_sql_console", Checkbox).value

            try:
                min_pwd_len = int(min_pwd_len_str)
                if min_pwd_len < 1:
                    raise ValueError()
            except ValueError:
                self.app.notify(
                    "Minimum Password Length must be at least 1.", severity="error"
                )
                return

            login_limit = self._parse_non_neg_int(login_limit_str, "Max Login Attempts")

            services.set_setting("min_password_length", str(min_pwd_len))
            services.set_setting("login_attempt_limit", str(login_limit))
            services.set_setting(
                "sql_console_enabled", "true" if sql_console_enabled else "false"
            )
            self.app.notify(
                "Security settings saved. SQL Console changes take effect on next login."
            )
        except ValueError as e:
            self.app.notify(str(e), severity="error")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    def save_api_key(self):
        """
        Persists the API key as a sensitive setting. If a key was already stored,
        the new value overwrites it. The input is cleared after saving so the
        raw value is never left visible on screen.
        """
        key_input = self.query_one("#setting_resend_api_key_input", Input)
        new_key = key_input.value.strip()
        if not new_key:
            self.app.notify("API key cannot be empty.", severity="warning")
            return
        services.set_sensitive_setting("resend_api_key", new_key)
        key_input.value = ""
        key_input.placeholder = "Key configured - paste new key to replace"
        self.app.notify("API key saved.")

    def save_settings_email(self):
        """Validates and persists Email and Notifications settings."""
        try:
            from_email = self.query_one("#setting_from_email", Input).value.strip()
            to_email = self.query_one("#setting_to_email", Input).value.strip()
            send_time = self.query_one("#setting_report_send_time", Input).value.strip()
            enabled = self.query_one("#setting_email_reports_enabled", Checkbox).value

            if to_email:
                try:
                    from email_validator import validate_email

                    validate_email(to_email, check_deliverability=False)
                except Exception:
                    self.app.notify(
                        "Report To must be a valid email address.", severity="error"
                    )
                    return

            if from_email:
                try:
                    from email_validator import validate_email

                    validate_email(from_email, check_deliverability=False)
                except Exception:
                    self.app.notify(
                        "From Email must be a valid email address.", severity="error"
                    )
                    return

            # Validate HH:MM format before saving
            try:
                from datetime import datetime as _dt

                _dt.strptime(send_time, "%H:%M")
            except ValueError:
                self.app.notify(
                    "Send Time must be in 24-hour HH:MM format, e.g. 07:00.",
                    severity="error",
                )
                return

            services.set_setting("report_from_email", from_email)
            services.set_setting("report_to_email", to_email)
            services.set_setting("report_send_time", send_time)
            services.set_setting(
                "email_reports_enabled", "true" if enabled else "false"
            )
            self.app.notify("Email settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving email settings: {str(e)}", severity="error")

    def send_test_email(self):
        """Saves current email settings then sends a test report for immediate feedback."""
        self.save_settings_email()
        from core.email_service import send_daily_report

        try:
            sent = send_daily_report()
            if sent:
                self.app.notify("Test email sent successfully.")
            else:
                self.app.notify(
                    "Email not sent: reports disabled or required settings missing.",
                    severity="warning",
                )
        except Exception as exc:
            self.app.notify(f"Email error: {exc}", severity="error")

    # ---------------------------------------------------------------------------
    # POS / Manual Transaction methods
    # ---------------------------------------------------------------------------

    def load_pos_transactions(self):
        """Loads the 50 most recent SquareTransaction records into the POS table."""
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
            table.add_row(
                str(t.id),
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.customer_name or "",
                f"${t.amount:.2f}",
                (t.description or "")[:28],
                t.square_status.replace("_", " ").title(),
                via,
            )

    def process_manual_transaction(self):
        """
        Reads the manual transaction form, validates inputs, and either sends a
        checkout request to the Square Terminal or records a local transaction
        depending on whether Square is enabled in POS settings.
        """
        try:
            amount_str = self.query_one("#pos_amount", Input).value.strip()
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
            description = self.query_one("#pos_description", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not amount_str:
            self.app.notify("Amount is required.", severity="error")
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            self.app.notify("Amount must be a positive number.", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        ok, message, txn = square_service.process_terminal_checkout(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            self.clear_pos_form()
            self.load_pos_transactions()

    def record_cash_transaction(self):
        """
        Reads the manual transaction form and records a cash payment either to
        Square (if enabled and configured) or locally. When recorded in Square,
        the transaction appears in Square Dashboard so the bookkeeper only needs
        to reconcile one system.
        """
        try:
            amount_str = self.query_one("#pos_amount", Input).value.strip()
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
            description = self.query_one("#pos_description", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not amount_str:
            self.app.notify("Amount is required.", severity="error")
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            self.app.notify("Amount must be a positive number.", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        ok, message, txn = square_service.record_cash_payment(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            self.clear_pos_form()
            self.load_pos_transactions()

    def clear_pos_form(self):
        """Resets all manual transaction input fields to their empty state."""
        for field_id in (
            "pos_amount",
            "pos_customer_name",
            "pos_customer_email",
            "pos_customer_phone",
            "pos_description",
        ):
            try:
                self.query_one(f"#{field_id}", Input).value = ""
            except Exception:
                pass

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

    # ---------------------------------------------------------------------------
    # POS settings save methods
    # ---------------------------------------------------------------------------

    def save_square_token(self, environment: str):
        """
        Persists the Square access token for the given environment ("sandbox" or
        "production") as a write-only credential. The input is cleared after saving
        so the raw value is never left visible on screen. The other environment's
        token is unaffected, so operators can switch freely without re-entering keys.
        """
        input_id = (
            "#setting_square_token_production"
            if environment == "production"
            else "#setting_square_token_sandbox"
        )
        token_input = self.query_one(input_id, Input)
        new_token = token_input.value.strip()
        if not new_token:
            self.app.notify("Access token cannot be empty.", severity="warning")
            return
        square_service.save_pos_access_token(new_token, environment)
        token_input.value = ""
        token_input.placeholder = (
            "Production token configured - paste to replace"
            if environment == "production"
            else "Sandbox token configured - paste to replace"
        )
        self.app.notify(f"Square {environment} token saved.")

    def save_pos_settings(self):
        """Validates and persists Point of Sale configuration settings."""
        try:
            enabled = self.query_one("#setting_square_enabled", Checkbox).value
            environment = (
                self.query_one("#setting_square_env", Select).value or "sandbox"
            )
            location_id = self.query_one(
                "#setting_square_location_id", Input
            ).value.strip()
            device_id = self.query_one("#setting_square_device_id", Input).value.strip()
            currency = self.query_one("#setting_square_currency", Select).value or "CAD"

            if environment not in ("sandbox", "production"):
                self.app.notify(
                    "Environment must be sandbox or production.", severity="error"
                )
                return

            square_service.save_pos_config(
                enabled=enabled,
                environment=environment,
                location_id=location_id,
                device_id=device_id,
                currency=currency,
            )
            self.app.notify("POS settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving POS settings: {e}", severity="error")

    def pair_terminal(self):
        """
        Requests a Terminal API pairing code from Square and displays it on
        screen. The operator enters the code on the terminal device to complete
        pairing. Once entered, Check Pairing Status will fetch the device ID
        and auto-fill the Device ID field.
        """
        ok, result, code_id = square_service.create_device_pairing_code()
        if not ok:
            self.app.notify(f"Pairing failed: {result}", severity="error")
            return

        self._pos_pairing_code_id = code_id
        try:
            self.query_one("#lbl_pairing_code").update(
                f"Pairing code: {result}  (enter this on the terminal now)"
            )
            self.query_one("#btn_check_pairing").disabled = False
        except Exception:
            pass
        self.app.notify(f"Pairing code generated: {result}")

    def check_terminal_pairing(self):
        """
        Polls Square for the pairing status of the active device code.
        On success, auto-fills the Device ID field and clears the pairing code display.
        """
        if not self._pos_pairing_code_id:
            self.app.notify("Generate a pairing code first.", severity="warning")
            return

        paired, message, device_id = square_service.check_device_pairing_status(
            self._pos_pairing_code_id
        )
        self.app.notify(message, severity="information" if paired else "warning")

        if paired and device_id:
            try:
                self.query_one("#setting_square_device_id", Input).value = device_id
                self.query_one("#lbl_pairing_code").update(
                    f"Paired. Device ID auto-filled: {device_id} — click Save POS Settings to save it."
                )
                self.query_one("#btn_check_pairing").disabled = True
                self._pos_pairing_code_id = None
            except Exception:
                pass

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
            return  # User cancelled — do not sign in
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
        # "Signed In" is additive — it unions currently signed-in users with the
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
