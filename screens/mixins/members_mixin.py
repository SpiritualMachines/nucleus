"""Member management mixin for Dashboard.

Owns all member / staff-tools / profile tab behaviour, including pending
approvals, user search, credit/debit transactions, membership management,
day passes, and Square subscription actions.
Methods here expect ``self`` to be a live Dashboard instance so that
``self.query_one``, ``self.app``, etc. resolve correctly.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Select

from core import services, square_service
from core.config import settings
from screens.dashboard_modals import (
    ActivateSubscriptionModal,
    AddDayPassModal,
    AddMembershipModal,
    DayPassHistoryModal,
    ManageMembershipsModal,
    TransactionModal,
    ViewCreditsModal,
    VISIT_TYPES,
)


class MembersMixin:
    """Mixin providing member management, staff tools, and profile tab methods."""

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

    def load_pending(self):
        """Loads all pending user accounts into the pending approvals table."""
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
        """Reloads the members table using the active role filter checkboxes."""
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

    def action_staff_user_search(self):
        """Searches for users from the Staff Tools tab search box."""
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

    def refresh_after_manage(self, result: bool = False):
        """Refreshes the members table when a manage action reports a change."""
        if result:
            self.load_members()

    def refresh_profile(self, result: bool = False):
        """Refreshes the My Profile tab labels after an edit-profile action."""
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

    def update_pending_alert(self):
        """Updates the pending approvals alert banner with the current count."""
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

    def update_signin_button(self):
        """Updates the sign-in button label and variant to reflect current sign-in state."""
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
