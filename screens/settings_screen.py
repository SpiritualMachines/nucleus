"""
Settings widget for admin-only configuration management.

This module provides an embeddable settings panel that mounts directly inside
the Dashboard's Settings tab, keeping all navigation within the main tab bar.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    TextArea,
)

from core import services, square_service
from core.config import settings


class SettingsScreen(Widget):
    """Embeddable settings panel for admin users.

    Provides sidebar navigation between settings categories and persists
    all configuration values to the AppSettings table via core services.
    Mounts directly inside the Dashboard Settings tab rather than as a
    separate pushed screen.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        height: 1fr;
        width: 1fr;
    }

    #tbl_storage_units {
        height: 10;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #tbl_inventory_items {
        height: 12;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #setting_ascii_logo {
        height: 13;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #settings_layout {
        height: 1fr;
    }

    #settings_nav {
        width: 26;
        height: 100%;
        border-right: solid $secondary;
        background: $boost;
    }

    #settings_content {
        width: 1fr;
        height: 100%;
    }
    """

    # Track selected tier rows for the Product Categories settings panel
    selected_mem_tier_id = None
    selected_dp_tier_id = None
    # Track selected storage unit row in the Storage Units settings panel
    selected_storage_unit_id = None
    # Track selected inventory item row in the Inventory settings panel
    selected_inventory_item_id = None
    # Track active device pairing code ID for terminal pairing polling
    _pos_pairing_code_id = None

    # Maps settings nav ListItem IDs to their corresponding ContentSwitcher panel IDs.
    _SETTINGS_NAV_MAP = {
        "nav_settings_general": "settings_panel_general",
        "nav_settings_operations": "settings_panel_operations",
        "nav_settings_branding": "settings_panel_branding",
        "nav_settings_security": "settings_panel_security",
        "nav_settings_pos": "settings_panel_pos",
        "nav_settings_subscriptions": "settings_panel_subscriptions",
        "nav_settings_products": "settings_panel_products",
        "nav_settings_storage": "settings_panel_storage",
        "nav_settings_inventory": "settings_panel_inventory",
        "nav_settings_email": "settings_panel_email",
        "nav_settings_backup": "settings_panel_backup",
    }

    def compose(self) -> ComposeResult:
        """Build the settings panel layout with sidebar navigation and content panels."""
        with Horizontal(id="settings_layout"):
            with ListView(id="settings_nav"):
                yield ListItem(Label("General"), id="nav_settings_general")
                yield ListItem(Label("Operations"), id="nav_settings_operations")
                yield ListItem(Label("Branding"), id="nav_settings_branding")
                yield ListItem(Label("Security"), id="nav_settings_security")
                yield ListItem(Label("Point of Sale"), id="nav_settings_pos")
                yield ListItem(Label("Subscriptions"), id="nav_settings_subscriptions")
                yield ListItem(Label("Product Categories"), id="nav_settings_products")
                yield ListItem(Label("Storage Units"), id="nav_settings_storage")
                yield ListItem(Label("Inventory"), id="nav_settings_inventory")
                yield ListItem(
                    Label("Email and Notifications"), id="nav_settings_email"
                )
                yield ListItem(Label("Backup"), id="nav_settings_backup")

            with ContentSwitcher(
                initial="settings_panel_general", id="settings_content"
            ):
                # --- General ---
                with VerticalScroll(id="settings_panel_general"):
                    yield Label("General Settings", classes="title")

                    yield Label("Auto-Logout Timeout (minutes):")
                    yield Input(
                        services.get_setting("logout_timeout_minutes", "10"),
                        placeholder="e.g. 10",
                        id="setting_logout_minutes",
                        type="integer",
                    )

                    yield Button(
                        "Save General Settings",
                        variant="success",
                        id="btn_save_general",
                    )

                # --- Operations ---
                with VerticalScroll(id="settings_panel_operations"):
                    yield Label("Space Operations", classes="title")

                    yield Label(
                        "Membership Grace Period (days after expiry before role downgrade, 0 = immediate):"
                    )
                    yield Input(
                        services.get_setting("membership_grace_period_days", "0"),
                        placeholder="e.g. 0",
                        id="setting_grace_period",
                        type="integer",
                    )

                    yield Label("Day Pass Cost (currency units, 0 = free):")
                    yield Input(
                        services.get_setting("day_pass_cost_credits", "0"),
                        placeholder="e.g. 0",
                        id="setting_daypass_cost",
                        type="integer",
                    )

                    yield Label("Max Concurrent Sign-Ins (0 = unlimited):")
                    yield Input(
                        services.get_setting("max_concurrent_signins", "0"),
                        placeholder="e.g. 0",
                        id="setting_max_signins",
                        type="integer",
                    )

                    yield Label("Backup Retention (days to keep, 0 = keep all):")
                    yield Input(
                        services.get_setting("backup_retention_days", "30"),
                        placeholder="e.g. 30",
                        id="setting_backup_retention",
                        type="integer",
                    )

                    yield Button(
                        "Save Operations Settings",
                        variant="success",
                        id="btn_save_operations",
                    )

                # --- Branding ---
                with VerticalScroll(id="settings_panel_branding"):
                    yield Label("Branding and Reporting", classes="title")

                    yield Label("Hackspace Name:")
                    yield Input(
                        services.get_setting("hackspace_name", settings.HACKSPACE_NAME),
                        placeholder="e.g. City Hackerspace",
                        id="setting_hackspace_name",
                    )

                    yield Label(
                        "Tag Name (short label used on buttons, e.g. Makerspace):"
                    )
                    yield Input(
                        services.get_setting("tag_name", settings.TAG_NAME),
                        placeholder="e.g. Makerspace",
                        id="setting_tag_name",
                    )

                    yield Label("App Name:")
                    yield Input(
                        services.get_setting("app_name", settings.APP_NAME),
                        placeholder="e.g. Nucleus",
                        id="setting_app_name",
                    )

                    yield Label("ASCII Logo:")
                    yield TextArea(id="setting_ascii_logo")

                    yield Label(
                        "Currency Name (what your space calls its internal currency, e.g. Credits, Hackerbucks):"
                    )
                    yield Input(
                        services.get_setting("app_currency_name", "Credits"),
                        placeholder="e.g. Credits",
                        id="setting_currency_name",
                    )

                    yield Label("Default Export Format:")
                    yield Select(
                        [("CSV", "csv"), ("PDF", "pdf")],
                        id="setting_default_export",
                        value=services.get_setting("default_export_format", "csv"),
                    )

                    yield Label(
                        "PDF Report Header Text (shown below title on all PDF exports):"
                    )
                    yield Input(
                        services.get_setting("report_header_text", ""),
                        placeholder="e.g. City Hackerspace - Membership Reports",
                        id="setting_report_header",
                    )

                    yield Label("Staff Reply-To Email Address (optional):")
                    yield Input(
                        services.get_setting("staff_email", ""),
                        placeholder="e.g. staff@yourhackerspace.org",
                        id="setting_staff_email",
                    )

                    yield Button(
                        "Save Branding Settings",
                        variant="success",
                        id="btn_save_branding",
                    )

                # --- Security ---
                with VerticalScroll(id="settings_panel_security"):
                    yield Label("Security Settings", classes="title")

                    yield Label("Minimum Password Length:")
                    yield Input(
                        services.get_setting("min_password_length", "8"),
                        placeholder="e.g. 8",
                        id="setting_min_pwd_len",
                        type="integer",
                    )

                    yield Label(
                        "Max Login Attempts Before Lockout (0 = unlimited, lockout lasts 30 minutes):"
                    )
                    yield Input(
                        services.get_setting("login_attempt_limit", "0"),
                        placeholder="e.g. 0",
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
                with VerticalScroll(id="settings_panel_pos"):
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

                # --- Subscriptions ---
                with VerticalScroll(id="settings_panel_subscriptions"):
                    yield Label("Square Recurring Subscriptions", classes="title")
                    yield Label(
                        "Configure the Square subscription plan used when enrolling members."
                        " Create your plan and variation in the Square Dashboard first,"
                        " then paste the Variation ID here."
                    )

                    yield Label("")
                    yield Label("Plan Variation ID:")
                    yield Input(
                        services.get_setting(
                            "square_subscription_plan_variation_id", ""
                        ),
                        placeholder="e.g. D3KPJGMOWQQFJJGZIHHDBFDA",
                        id="setting_subscription_plan_id",
                    )

                    yield Label("Billing Timezone:")
                    yield Input(
                        services.get_setting(
                            "square_subscription_timezone", "America/Toronto"
                        ),
                        placeholder="e.g. America/Toronto",
                        id="setting_subscription_timezone",
                    )

                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Save Subscription Settings",
                            variant="success",
                            id="btn_save_subscription_settings",
                        )

                    yield Label("", classes="subtitle")
                    yield Label("Manual Poll", classes="subtitle")
                    yield Label(
                        "Check the current subscription status for all enrolled members."
                        " This runs automatically via scripts/poll_subscriptions.py."
                    )
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Poll All Subscriptions Now",
                            variant="primary",
                            id="btn_poll_all_subscriptions",
                        )
                    yield Label("", id="lbl_poll_result")

                # --- Product Categories ---
                with VerticalScroll(id="settings_panel_products"):
                    yield Label("Product Categories", classes="title")
                    yield Label(
                        "Define reusable tier templates for memberships and day passes."
                        " Selecting a tier in the Add Membership or Add Day Pass"
                        " dialogs will auto-fill price and duration."
                    )

                    # Membership Tiers section
                    yield Label("Membership Tiers", classes="subtitle")
                    yield DataTable(id="tbl_mem_tiers")
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Delete Selected",
                            id="btn_delete_mem_tier",
                            variant="error",
                        )
                    yield Label("Name:")
                    yield Input(placeholder="e.g. Monthly Standard", id="tier_mem_name")
                    yield Label("Price ($):")
                    yield Input(placeholder="0.00", type="number", id="tier_mem_price")
                    yield Label("Duration (days):")
                    yield Input(
                        placeholder="30", type="integer", id="tier_mem_duration"
                    )
                    yield Label("Consumables Credits (optional):")
                    yield Input(
                        placeholder="0.00", type="number", id="tier_mem_credits"
                    )
                    yield Label("Description (optional):")
                    yield Input(placeholder="", id="tier_mem_description")
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Membership Tier",
                            id="btn_add_mem_tier",
                            variant="success",
                        )

                    # Day Pass Tiers section
                    yield Label("Day Pass Tiers", classes="subtitle")
                    yield DataTable(id="tbl_dp_tiers")
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Delete Selected",
                            id="btn_delete_dp_tier",
                            variant="error",
                        )
                    yield Label("Name:")
                    yield Input(placeholder="e.g. Standard Day Pass", id="tier_dp_name")
                    yield Label("Price ($):")
                    yield Input(placeholder="0.00", type="number", id="tier_dp_price")
                    yield Label("Description (optional):")
                    yield Input(placeholder="", id="tier_dp_description")
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Day Pass Tier",
                            id="btn_add_dp_tier",
                            variant="success",
                        )

                # --- Storage Units ---
                with VerticalScroll(id="settings_panel_storage"):
                    yield Label("Storage Units", classes="title")
                    yield Label(
                        "Create and delete storage units (bins, lockers, shelves)."
                        " Units with active assignments cannot be deleted."
                    )

                    yield DataTable(id="tbl_storage_units")

                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Delete Selected",
                            id="btn_delete_storage_unit",
                            variant="error",
                            disabled=True,
                        )

                    yield Label("Create Storage Unit", classes="subtitle")
                    yield Label("Unit Number (auto-filled, editable):")
                    yield Input(
                        services.get_next_storage_unit_number(),
                        placeholder="e.g. A-01",
                        id="storage_unit_number",
                    )
                    yield Label("Description (auto-filled, editable):")
                    yield Input(
                        "Storage Bin",
                        placeholder="e.g. Storage Bin",
                        id="storage_unit_description",
                    )
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Create Storage Unit",
                            id="btn_create_storage_unit",
                            variant="success",
                        )

                # --- Inventory ---
                with VerticalScroll(id="settings_panel_inventory"):
                    yield Label("Inventory Items", classes="title")
                    yield Label(
                        "Define items that staff can select when processing"
                        " transactions. Items appear in the inventory cart"
                        " in the Purchases tab."
                    )

                    yield DataTable(id="tbl_inventory_items")
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Delete Selected",
                            id="btn_delete_inventory_item",
                            variant="error",
                            disabled=True,
                        )

                    yield Label("Add Inventory Item", classes="subtitle")
                    yield Label("Name:")
                    yield Input(
                        placeholder="e.g. 3D Print Filament or Chips",
                        id="inv_item_name",
                    )
                    yield Label("Description (optional):")
                    yield Input(placeholder="", id="inv_item_description")
                    yield Label("Price ($):")
                    yield Input(
                        placeholder="0.00",
                        id="inv_item_price",
                        type="number",
                    )
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Item",
                            id="btn_add_inventory_item",
                            variant="success",
                        )

                # --- Email and Notifications ---
                with VerticalScroll(id="settings_panel_email"):
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

                    yield Label(
                        "Send Daily Report To (comma-separated email addresses):"
                    )
                    yield Input(
                        services.get_setting("report_to_email", ""),
                        placeholder="e.g. admin@yourhackerspace.org, reports@yourhackerspace.org",
                        id="setting_to_email",
                    )

                    yield Label("Daily Report Send Time (24-hour HH:MM, e.g. 07:00):")
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

                    yield Checkbox(
                        "Email receipts to customers after each transaction",
                        id="setting_email_receipts_enabled",
                        value=services.get_setting(
                            "email_receipts_enabled", "false"
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

                # --- Backup ---
                with VerticalScroll(id="settings_panel_backup"):
                    yield Label("Backup", classes="title")

                    yield Checkbox(
                        "Enable automatic backups",
                        value=services.get_setting("backup_enabled", "false").lower()
                        == "true",
                        id="setting_backup_enabled",
                    )

                    yield Label("Backup Time (24-hour HH:MM, e.g. 02:00):")
                    yield Input(
                        services.get_setting("backup_time", "02:00"),
                        placeholder="e.g. 02:00",
                        id="setting_backup_time",
                    )

                    yield Label("Backup Retention (days to keep, 0 = keep all):")
                    yield Input(
                        services.get_setting("backup_retention_days", "30"),
                        placeholder="e.g. 30",
                        id="setting_backup_retention",
                        type="integer",
                    )

                    yield Label(
                        "Email Backup To (optional, comma-separated for multiple):"
                    )
                    yield Input(
                        services.get_setting("backup_email", ""),
                        placeholder="e.g. admin@yourhackerspace.org",
                        id="setting_backup_email",
                    )

                    yield Button(
                        "Save Backup Settings",
                        variant="success",
                        id="btn_save_backup",
                    )

    def on_mount(self) -> None:
        """Initialize settings table columns and pre-load data after the screen mounts."""
        mem_tiers_table = self.query_one("#tbl_mem_tiers", DataTable)
        if mem_tiers_table:
            mem_tiers_table.add_columns(
                "ID", "Name", "Price", "Duration (days)", "Credits", "Description"
            )
            mem_tiers_table.cursor_type = "row"

        dp_tiers_table = self.query_one("#tbl_dp_tiers", DataTable)
        if dp_tiers_table:
            dp_tiers_table.add_columns("ID", "Name", "Price", "Description")
            dp_tiers_table.cursor_type = "row"

        self.load_product_tiers()

        storage_units_table = self.query_one("#tbl_storage_units", DataTable)
        if storage_units_table:
            storage_units_table.add_columns("ID", "Unit Number", "Description")
            storage_units_table.cursor_type = "row"

        self.load_storage_units_settings()

        inv_settings_table = self.query_one("#tbl_inventory_items", DataTable)
        if inv_settings_table:
            inv_settings_table.add_columns("ID", "Name", "Description", "Price")
            inv_settings_table.cursor_type = "row"

        self.load_inventory_settings()

        # Defer ASCII logo load until layout has computed panel dimensions,
        # because TextArea.wrap_width is zero while the panel is hidden.
        self.call_after_refresh(self._load_ascii_logo_if_needed)

        # Cache the button-press dispatch table so lookups are O(1)
        self._dispatch = self._build_dispatch()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Switch the visible settings panel when a nav item is chosen."""
        panel_id = self._SETTINGS_NAV_MAP.get(event.item.id)
        if panel_id is None:
            return
        self.query_one("#settings_content", ContentSwitcher).current = panel_id
        # The ASCII logo TextArea needs a deferred load because its wrap_width
        # is zero while the panel is hidden; trigger once the layout recalculates.
        if panel_id == "settings_panel_branding":
            self.call_after_refresh(self._load_ascii_logo_if_needed)

    def _load_ascii_logo_if_needed(self) -> None:
        """Loads the stored ASCII logo into the TextArea if it has not yet been populated."""
        results = self.query("#setting_ascii_logo")
        if not results:
            return
        logo_area = results.first(TextArea)
        if not logo_area.text:
            logo_area.load_text(services.get_setting("ascii_logo", settings.ASCII_LOGO))

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

    def _build_dispatch(self) -> dict:
        """Build and return a mapping of button IDs to handler callables.

        Centralises all button-press routing so that on_button_pressed can
        perform a single dictionary lookup instead of a long if/elif chain.
        """
        return {
            # General / Operations / Branding / Security
            "btn_save_general": self.save_settings_general,
            "btn_save_operations": self.save_settings_operations,
            "btn_save_branding": self.save_settings_branding,
            "btn_save_security": self.save_settings_security,
            "btn_save_api_key": self.save_api_key,
            # Email and Backup
            "btn_save_email": self.save_settings_email,
            "btn_test_email": self.send_test_email,
            "btn_save_backup": self.save_settings_backup,
            # Subscription settings
            "btn_save_subscription_settings": self.save_subscription_settings,
            "btn_poll_all_subscriptions": self.poll_all_subscriptions,
            # Storage settings
            "btn_create_storage_unit": self.create_storage_unit,
            "btn_delete_storage_unit": self.delete_storage_unit,
            # Inventory settings
            "btn_add_inventory_item": self.create_inventory_item_action,
            "btn_delete_inventory_item": self.delete_inventory_item_action,
            # POS settings
            "btn_save_square_token_sandbox": self._handle_save_square_token_sandbox,
            "btn_save_square_token_production": self._handle_save_square_token_production,
            "btn_save_pos_settings": self.save_pos_settings,
            "btn_pair_terminal": self.pair_terminal,
            "btn_check_pairing": self.check_terminal_pairing,
            # Product tier management
            "btn_add_mem_tier": self._add_membership_tier,
            "btn_delete_mem_tier": self._delete_membership_tier,
            "btn_add_dp_tier": self._add_daypass_tier,
            "btn_delete_dp_tier": self._delete_daypass_tier,
        }

    def _handle_save_square_token_sandbox(self) -> None:
        """Delegates to save_square_token for the sandbox environment."""
        self.save_square_token("sandbox")

    def _handle_save_square_token_production(self) -> None:
        """Delegates to save_square_token for the production environment."""
        self.save_square_token("production")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to the appropriate settings action handler."""
        handler = self._dispatch.get(event.button.id)
        if handler:
            handler()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Track the selected row for each settings-owned table."""
        if event.data_table.id == "tbl_mem_tiers":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_mem_tier_id = int(row_data[0])

        elif event.data_table.id == "tbl_dp_tiers":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_dp_tier_id = int(row_data[0])

        elif event.data_table.id == "tbl_storage_units":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_storage_unit_id = int(row_data[0])
            self.query_one("#btn_delete_storage_unit").disabled = False

        elif event.data_table.id == "tbl_inventory_items":
            row_data = event.data_table.get_row(event.row_key)
            self.selected_inventory_item_id = int(row_data[0])
            self.query_one("#btn_delete_inventory_item").disabled = False

    # ---------------------------------------------------------------------------
    # General settings
    # ---------------------------------------------------------------------------

    def save_settings_general(self) -> None:
        """Validates and persists General settings, applying changes live where possible."""
        try:
            logout_minutes_str = self.query_one("#setting_logout_minutes").value.strip()

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

            services.set_setting("logout_timeout_minutes", str(logout_minutes))
            self.app.notify("General settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    # ---------------------------------------------------------------------------
    # Operations settings
    # ---------------------------------------------------------------------------

    def save_settings_operations(self) -> None:
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

    # ---------------------------------------------------------------------------
    # Branding settings
    # ---------------------------------------------------------------------------

    def save_settings_branding(self) -> None:
        """Validates and persists Branding and Reporting settings."""
        try:
            hackspace_name = self.query_one("#setting_hackspace_name").value.strip()
            tag_name = self.query_one("#setting_tag_name").value.strip()
            app_name = self.query_one("#setting_app_name").value.strip()
            ascii_logo = self.query_one("#setting_ascii_logo", TextArea).text
            currency_name = self.query_one("#setting_currency_name").value.strip()
            default_export = (
                self.query_one("#setting_default_export", Select).value or "csv"
            )
            report_header = self.query_one("#setting_report_header").value.strip()
            staff_email = self.query_one("#setting_staff_email").value.strip()

            if not hackspace_name:
                self.app.notify("Hackspace Name cannot be empty.", severity="error")
                return
            if not tag_name:
                self.app.notify("Tag Name cannot be empty.", severity="error")
                return
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

            services.set_setting("hackspace_name", hackspace_name)
            services.set_setting("tag_name", tag_name)
            services.set_setting("app_name", app_name)
            services.set_setting("ascii_logo", ascii_logo)
            services.set_setting("app_currency_name", currency_name)
            services.set_setting("default_export_format", default_export)
            services.set_setting("report_header_text", report_header)
            services.set_setting("staff_email", staff_email)
            self.app.title = hackspace_name
            # Propagate the sign-in button label change to Dashboard if it is
            # currently in the screen stack.
            try:
                from screens.dashboard import Dashboard

                self.app.query_one(Dashboard).update_signin_button()
            except Exception:
                pass
            self.app.notify("Branding settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    # ---------------------------------------------------------------------------
    # Security settings
    # ---------------------------------------------------------------------------

    def save_settings_security(self) -> None:
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

    # ---------------------------------------------------------------------------
    # API key
    # ---------------------------------------------------------------------------

    def save_api_key(self) -> None:
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

    # ---------------------------------------------------------------------------
    # Email settings
    # ---------------------------------------------------------------------------

    def save_settings_email(self) -> None:
        """Validates and persists Email and Notifications settings."""
        try:
            from_email = self.query_one("#setting_from_email", Input).value.strip()
            to_email = self.query_one("#setting_to_email", Input).value.strip()
            send_time = self.query_one("#setting_report_send_time", Input).value.strip()
            enabled = self.query_one("#setting_email_reports_enabled", Checkbox).value
            receipts_enabled = self.query_one(
                "#setting_email_receipts_enabled", Checkbox
            ).value

            if to_email:
                from email_validator import validate_email

                for addr in to_email.split(","):
                    addr = addr.strip()
                    if not addr:
                        continue
                    try:
                        validate_email(addr, check_deliverability=False)
                    except Exception:
                        self.app.notify(
                            f"Invalid email address: {addr}", severity="error"
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
            services.set_setting(
                "email_receipts_enabled", "true" if receipts_enabled else "false"
            )
            self.app.notify("Email settings saved.")
        except Exception as e:
            self.app.notify(f"Error saving email settings: {str(e)}", severity="error")

    def send_test_email(self) -> None:
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

    def save_settings_backup(self) -> None:
        """Validates and persists Backup settings."""
        try:
            from email_validator import validate_email

            enabled = self.query_one("#setting_backup_enabled", Checkbox).value
            backup_time = self.query_one("#setting_backup_time", Input).value.strip()
            backup_retention = self._parse_non_neg_int(
                self.query_one("#setting_backup_retention", Input).value.strip(),
                "Backup Retention",
            )
            backup_email = self.query_one("#setting_backup_email", Input).value.strip()

            # Validate HH:MM format
            if backup_time:
                try:
                    parts = backup_time.split(":")
                    if (
                        len(parts) != 2
                        or not (0 <= int(parts[0]) <= 23)
                        or not (0 <= int(parts[1]) <= 59)
                    ):
                        raise ValueError
                except (ValueError, IndexError):
                    self.app.notify(
                        "Backup Time must be in 24-hour HH:MM format (e.g. 02:00).",
                        severity="error",
                    )
                    return

            # Validate each comma-separated backup email address
            if backup_email:
                for addr in backup_email.split(","):
                    addr = addr.strip()
                    if not addr:
                        continue
                    try:
                        validate_email(addr, check_deliverability=False)
                    except Exception:
                        self.app.notify(
                            f"Backup Email contains an invalid address: {addr}",
                            severity="error",
                        )
                        return

            services.set_setting("backup_enabled", "true" if enabled else "false")
            services.set_setting("backup_time", backup_time or "02:00")
            services.set_setting("backup_retention_days", str(backup_retention))
            services.set_setting("backup_email", backup_email)
            self.app.notify("Backup settings saved.")
        except ValueError as e:
            self.app.notify(str(e), severity="error")
        except Exception as e:
            self.app.notify(f"Error saving settings: {str(e)}", severity="error")

    # ---------------------------------------------------------------------------
    # Subscription settings
    # ---------------------------------------------------------------------------

    def save_subscription_settings(self) -> None:
        """Persists the Square subscription plan variation ID and timezone to AppSettings."""
        try:
            plan_id = self.query_one(
                "#setting_subscription_plan_id", Input
            ).value.strip()
            timezone = self.query_one(
                "#setting_subscription_timezone", Input
            ).value.strip()
            services.set_setting("square_subscription_plan_variation_id", plan_id)
            services.set_setting(
                "square_subscription_timezone",
                timezone or "America/Toronto",
            )
            self.app.notify("Subscription settings saved.")
        except Exception as e:
            self.app.notify(
                f"Error saving subscription settings: {str(e)}", severity="error"
            )

    def poll_all_subscriptions(self) -> None:
        """Runs a manual status poll for all members with a Square subscription on file."""
        try:
            polled, errors = square_service.poll_all_active_subscriptions()
            msg = f"Poll complete: {polled} updated, {errors} errors."
            self.query_one("#lbl_poll_result", Label).update(msg)
            severity = "warning" if errors else "information"
            self.app.notify(msg, severity=severity)
        except Exception as e:
            self.app.notify(f"Poll failed: {str(e)}", severity="error")

    # ---------------------------------------------------------------------------
    # Product Tier methods
    # ---------------------------------------------------------------------------

    def load_product_tiers(self) -> None:
        """
        Clears and repopulates the membership and day pass tier tables from the
        database. Called on mount and after any add or delete operation.
        """
        mem_table = self.query_one("#tbl_mem_tiers", DataTable)
        mem_table.clear()
        for tier in services.get_product_tiers("membership"):
            mem_table.add_row(
                str(tier.id),
                tier.name,
                f"${tier.price:.2f}",
                str(tier.duration_days) if tier.duration_days is not None else "",
                f"${tier.consumables_credits:.2f}" if tier.consumables_credits else "",
                tier.description or "",
                key=str(tier.id),
            )

        dp_table = self.query_one("#tbl_dp_tiers", DataTable)
        dp_table.clear()
        for tier in services.get_product_tiers("daypass"):
            dp_table.add_row(
                str(tier.id),
                tier.name,
                f"${tier.price:.2f}",
                tier.description or "",
                key=str(tier.id),
            )

    def _add_membership_tier(self) -> None:
        """Validates form inputs and saves a new membership tier to the database."""
        name = self.query_one("#tier_mem_name", Input).value.strip()
        price_str = self.query_one("#tier_mem_price", Input).value.strip()
        duration_str = self.query_one("#tier_mem_duration", Input).value.strip()
        credits_str = self.query_one("#tier_mem_credits", Input).value.strip()
        description = (
            self.query_one("#tier_mem_description", Input).value.strip() or None
        )

        if not name:
            self.app.notify("Tier name is required.", severity="error")
            return
        try:
            price = float(price_str) if price_str else 0.0
            duration_days = int(duration_str) if duration_str else None
            consumables_credits = float(credits_str) if credits_str else None
        except ValueError:
            self.app.notify(
                "Invalid price, duration, or credits value.", severity="error"
            )
            return

        services.save_product_tier(
            name=name,
            tier_type="membership",
            price=price,
            duration_days=duration_days,
            consumables_credits=consumables_credits,
            description=description,
        )
        self.app.notify(f"Membership tier '{name}' added.")
        self.query_one("#tier_mem_name", Input).value = ""
        self.query_one("#tier_mem_price", Input).value = ""
        self.query_one("#tier_mem_duration", Input).value = ""
        self.query_one("#tier_mem_credits", Input).value = ""
        self.query_one("#tier_mem_description", Input).value = ""
        self.load_product_tiers()

    def _delete_membership_tier(self) -> None:
        """Deletes the currently selected membership tier row."""
        if self.selected_mem_tier_id is None:
            self.app.notify("Select a tier row first.", severity="warning")
            return
        deleted = services.delete_product_tier(self.selected_mem_tier_id)
        if deleted:
            self.app.notify("Membership tier deleted.")
            self.selected_mem_tier_id = None
        else:
            self.app.notify("Tier not found.", severity="error")
        self.load_product_tiers()

    def _add_daypass_tier(self) -> None:
        """Validates form inputs and saves a new day pass tier to the database."""
        name = self.query_one("#tier_dp_name", Input).value.strip()
        price_str = self.query_one("#tier_dp_price", Input).value.strip()
        description = (
            self.query_one("#tier_dp_description", Input).value.strip() or None
        )

        if not name:
            self.app.notify("Tier name is required.", severity="error")
            return
        try:
            price = float(price_str) if price_str else 0.0
        except ValueError:
            self.app.notify("Invalid price value.", severity="error")
            return

        services.save_product_tier(
            name=name,
            tier_type="daypass",
            price=price,
            duration_days=None,
            consumables_credits=None,
            description=description,
        )
        self.app.notify(f"Day pass tier '{name}' added.")
        self.query_one("#tier_dp_name", Input).value = ""
        self.query_one("#tier_dp_price", Input).value = ""
        self.query_one("#tier_dp_description", Input).value = ""
        self.load_product_tiers()

    def _delete_daypass_tier(self) -> None:
        """Deletes the currently selected day pass tier row."""
        if self.selected_dp_tier_id is None:
            self.app.notify("Select a tier row first.", severity="warning")
            return
        deleted = services.delete_product_tier(self.selected_dp_tier_id)
        if deleted:
            self.app.notify("Day pass tier deleted.")
            self.selected_dp_tier_id = None
        else:
            self.app.notify("Tier not found.", severity="error")
        self.load_product_tiers()

    # ---------------------------------------------------------------------------
    # POS settings save methods
    # ---------------------------------------------------------------------------

    def save_square_token(self, environment: str) -> None:
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

    def save_pos_settings(self) -> None:
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

    def pair_terminal(self) -> None:
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

    def check_terminal_pairing(self) -> None:
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

    # ---------------------------------------------------------------------------
    # Storage settings
    # ---------------------------------------------------------------------------

    def load_storage_units_settings(self) -> None:
        """Loads all active storage units into the Settings > Storage Units table."""
        try:
            table = self.query_one("#tbl_storage_units", DataTable)
        except Exception:
            return
        table.clear()
        units = services.get_all_storage_units()
        for u in units:
            table.add_row(str(u.id), u.unit_number, u.description)

    def create_storage_unit(self) -> None:
        """Reads the settings form inputs and creates a new storage unit."""
        unit_number = self.query_one("#storage_unit_number", Input).value.strip()
        description = self.query_one("#storage_unit_description", Input).value.strip()
        if not unit_number:
            self.app.notify("Unit number is required.", severity="error")
            return
        services.create_storage_unit(
            unit_number=unit_number, description=description or "Storage Bin"
        )
        self.app.notify(f"Storage unit {unit_number} created.")
        # Advance the auto-fill to the next number and reload the table
        next_num = services.get_next_storage_unit_number()
        self.query_one("#storage_unit_number", Input).value = next_num
        self.query_one("#storage_unit_description", Input).value = "Storage Bin"
        self.load_storage_units_settings()

    def delete_storage_unit(self) -> None:
        """Deletes the selected storage unit if it has no active assignments."""
        if not self.selected_storage_unit_id:
            self.app.notify("Select a storage unit first.", severity="warning")
            return
        ok = services.delete_storage_unit(self.selected_storage_unit_id)
        if ok:
            self.app.notify("Storage unit deleted.")
            self.selected_storage_unit_id = None
            self.query_one("#btn_delete_storage_unit").disabled = True
        else:
            self.app.notify(
                "Cannot delete: unit has active assignments. Archive them first.",
                severity="error",
            )
        self.load_storage_units_settings()

    # ---------------------------------------------------------------------------
    # Inventory settings
    # ---------------------------------------------------------------------------

    def load_inventory_settings(self) -> None:
        """Loads all active inventory items into the Settings > Inventory table."""
        try:
            table = self.query_one("#tbl_inventory_items", DataTable)
        except Exception:
            return
        table.clear()
        for item in services.get_all_inventory_items():
            table.add_row(
                str(item.id), item.name, item.description or "", f"${item.price:.2f}"
            )

    def create_inventory_item_action(self) -> None:
        """Reads the settings form and creates a new inventory item."""
        name = self.query_one("#inv_item_name", Input).value.strip()
        if not name:
            self.app.notify("Name is required.", severity="error")
            return
        description = (
            self.query_one("#inv_item_description", Input).value.strip() or None
        )
        try:
            price = float(self.query_one("#inv_item_price", Input).value or "0")
        except ValueError:
            self.app.notify("Enter a valid price.", severity="error")
            return
        services.create_inventory_item(name=name, description=description, price=price)
        self.app.notify(f"Item '{name}' added.")
        self.query_one("#inv_item_name", Input).value = ""
        self.query_one("#inv_item_description", Input).value = ""
        self.query_one("#inv_item_price", Input).value = ""
        self.load_inventory_settings()
        # Attempt to refresh the Purchases tab available-items table if Dashboard
        # is in the stack; fail silently if it is not present.
        try:
            from screens.dashboard import Dashboard

            self.app.query_one(Dashboard)._load_inv_available_table()
        except Exception:
            pass

    def delete_inventory_item_action(self) -> None:
        """Deletes the selected inventory item from settings."""
        if not self.selected_inventory_item_id:
            self.app.notify("Select an item first.", severity="warning")
            return
        services.delete_inventory_item(self.selected_inventory_item_id)
        self.app.notify("Item deleted.")
        self.selected_inventory_item_id = None
        self.query_one("#btn_delete_inventory_item").disabled = True
        self.load_inventory_settings()
        # Attempt to refresh the Purchases tab available-items table if Dashboard
        # is in the stack; fail silently if it is not present.
        try:
            from screens.dashboard import Dashboard

            self.app.query_one(Dashboard)._load_inv_available_table()
        except Exception:
            pass
