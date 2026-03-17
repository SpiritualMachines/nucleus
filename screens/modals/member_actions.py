"""Member action modal and staff user editing for the dashboard."""

__all__ = [
    "MemberActionModal",
    "StaffEditUserScreen",
    "ManageSignInsModal",
]

from datetime import datetime

from sqlmodel import Session, desc, select
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, OptionList, Select

from core import models, services
from core.database import engine
from screens.modals import MEMBER_ACTIONS, VISIT_TYPES, get_safe_role_name


class MemberActionModal(ModalScreen):
    """
    Modal that appears when clicking a user row in the Staff > Reports table.
    Offers choices: Edit Profile, Manage Memberships, Manage Balances, etc.
    """

    def __init__(self, acct_num: str, name: str):
        super().__init__()
        self.acct_num = int(acct_num)
        self.target_name = name

    def compose(self) -> ComposeResult:
        target_user = services.get_user_by_account(self.acct_num)

        # --- FIX: Safe Role Access ---
        role_display = "Unknown"
        if target_user:
            role_display = get_safe_role_name(target_user.role)
        # -----------------------------

        with Vertical(classes="splash-container"):
            yield Label(f"Manage: {self.target_name}", classes="title")
            yield Label(f"Account #: {self.acct_num}", classes="subtitle")
            yield Label(f"Role: {role_display}", classes="subtitle")
            yield Label("Select Action:", classes="subtitle")
            yield OptionList(*MEMBER_ACTIONS, id="action_list")
            with Horizontal(classes="filter-row"):
                yield Button("Close", variant="error", id="btn_close")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        # Lazy imports to avoid circular dependencies between sub-modules
        from screens.modals.day_pass import AddDayPassModal, DayPassHistoryModal
        from screens.modals.membership import AddMembershipModal, ManageMembershipsModal
        from screens.modals.subscriptions import ActivateSubscriptionModal
        from screens.modals.transactions import TransactionModal

        idx = event.option_index
        if idx == 0:
            self.app.push_screen(StaffEditUserScreen(self.acct_num), self.chain_refresh)
        elif idx == 1:
            self.app.push_screen(AddMembershipModal(self.acct_num), self.chain_refresh)
        elif idx == 2:
            self.app.push_screen(
                ManageMembershipsModal(self.acct_num), self.chain_refresh
            )
        elif idx == 3:
            currency = services.get_setting("app_currency_name", "Credits")
            self.app.push_screen(
                TransactionModal(self.acct_num, "credit", currency), self.chain_refresh
            )
        elif idx == 4:
            self.app.push_screen(AddDayPassModal(self.acct_num), self.chain_refresh)
        elif idx == 5:
            self.app.push_screen(DayPassHistoryModal(self.acct_num))
        elif idx == 6:
            self.app.push_screen(ManageSignInsModal(self.acct_num))
        elif idx == 7:
            self.app.push_screen(
                ActivateSubscriptionModal(self.acct_num), self.chain_refresh
            )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)

    def chain_refresh(self, result=False):
        """Passes True back to Dashboard if any action happened."""
        if result:
            self.dismiss(True)


class StaffEditUserScreen(ModalScreen):
    """Staff modal to edit another user's details and ROLE."""

    def __init__(self, target_acct: int):
        super().__init__()
        self.target_acct = target_acct

    def compose(self) -> ComposeResult:
        user = services.get_user_by_account(self.target_acct)

        with Vertical(classes="splash-container"):
            yield Label(f"Editing User #{self.target_acct}", classes="title")

            with VerticalScroll(classes="splash-content"):
                yield Label("System Role:", classes="subtitle")

                # --- FIX: Handle raw string role for Select default value ---
                current_role_val = (
                    user.role.value if hasattr(user.role, "value") else str(user.role)
                )

                yield Select.from_values(
                    [r.value for r in models.UserRole],
                    value=current_role_val,
                    id="edit_role",
                )

                yield Label("First Name:")
                yield Input(user.first_name, id="edit_fname")
                yield Label("Last Name:")
                yield Input(user.last_name, id="edit_lname")
                yield Label("Email:")
                yield Input(user.email, id="edit_email")

                yield Label("Staff Comments / Warnings:", classes="subtitle")
                yield Input(user.account_comments or "", id="edit_comments")

            with Horizontal(classes="filter-row"):
                yield Button("Save Changes", variant="success", id="btn_save")
                yield Button("Cancel", variant="error", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            self.save_changes()

    def save_changes(self):
        try:
            new_role_str = self.query_one("#edit_role").value

            # Prevent demoting the last admin (basic check)
            if (
                new_role_str == models.UserRole.ADMIN.value
                and self.app.current_user.role != models.UserRole.ADMIN
            ):
                self.app.notify("Only Admins can promote to Admin.", severity="error")
                return

            data = {
                "role": new_role_str,
                "first_name": self.query_one("#edit_fname").value,
                "last_name": self.query_one("#edit_lname").value,
                "email": self.query_one("#edit_email").value,
                "account_comments": self.query_one("#edit_comments").value,
            }

            services.update_user_details(self.target_acct, data)
            self.app.notify("User Updated.")
            self.dismiss(True)
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")


class ManageSignInsModal(ModalScreen):
    """
    Modal to view, edit, add, or delete sign-in records for a user.
    Caps the table height so the edit fields below it always remain visible.
    """

    CSS = """
    ManageSignInsModal #table_section {
        height: 12;
        border: solid $secondary;
        background: $boost;
        padding: 1;
        margin: 1 0;
    }
    ManageSignInsModal #edit_section {
        height: auto;
        border-top: solid $secondary;
        padding-top: 1;
        margin-top: 1;
    }
    """

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.selected_signin_id = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label(f"Manage Sign Ins: Account {self.user_id}", classes="title")

            with Vertical(id="table_section"):
                yield DataTable(id="signin_table")

            # --- Editing Fields ---
            with Vertical(id="edit_section"):
                yield Label("Edit Selected Entry (or Add New):", classes="subtitle")
                yield Label("Sign In Time (YYYY-MM-DD HH:MM:SS):")
                yield Input(id="edit_in_time")
                yield Label(
                    "Sign Out Time (YYYY-MM-DD HH:MM:SS) - Leave blank if active:"
                )
                yield Input(id="edit_out_time")

                yield Label("Visit Type:")
                yield Select(
                    [(vt, vt) for vt in VISIT_TYPES],
                    id="edit_visit_type",
                    allow_blank=True,
                )

                with Horizontal(classes="filter-row"):
                    yield Button(
                        "Save Changes", variant="success", id="btn_save", disabled=True
                    )
                    yield Button(
                        "Delete Entry", variant="error", id="btn_delete", disabled=True
                    )
                    yield Button("Add New Entry", variant="primary", id="btn_add")

            with Horizontal(classes="filter-row"):
                yield Button("Close", id="btn_close")

    def on_mount(self):
        table = self.query_one("#signin_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Sign In", "Sign Out", "Visit Type")
        self.load_data()

    def load_data(self):
        table = self.query_one("#signin_table", DataTable)
        table.clear()

        # We need to query SpaceAttendance manually here or add a service method.
        # Direct DB query for simplicity within this modal file.
        with Session(engine) as session:
            stmt = (
                select(models.SpaceAttendance)
                .where(models.SpaceAttendance.user_account_number == self.user_id)
                .order_by(desc(models.SpaceAttendance.sign_in_time))
            )

            attendance_records = session.exec(stmt).all()

            for att in attendance_records:
                in_time = att.sign_in_time.strftime("%Y-%m-%d %H:%M:%S")
                out_time = (
                    att.sign_out_time.strftime("%Y-%m-%d %H:%M:%S")
                    if att.sign_out_time
                    else "Active"
                )
                vtype = getattr(att, "visit_type", "") or ""
                table.add_row(str(att.id), in_time, out_time, vtype)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Populate fields when a row is clicked."""
        row_data = event.data_table.get_row(event.row_key)
        self.selected_signin_id = int(row_data[0])
        in_time_val = row_data[1]
        out_time_val = row_data[2] if row_data[2] != "Active" else ""
        vtype_val = row_data[3] if len(row_data) > 3 else ""

        self.query_one("#edit_in_time").value = in_time_val
        self.query_one("#edit_out_time").value = out_time_val

        # Set the visit type Select to match the stored value, or blank if unknown
        vtype_select = self.query_one("#edit_visit_type", Select)
        vtype_select.value = vtype_val if vtype_val in VISIT_TYPES else Select.BLANK

        self.query_one("#btn_save").disabled = False
        self.query_one("#btn_delete").disabled = False
        # When selecting a row, we are in "Edit Mode", so Add is less relevant, but kept enabled.

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            self.save_changes()
        elif event.button.id == "btn_delete":
            self.delete_entry()
        elif event.button.id == "btn_add":
            self.add_new_entry()

    def parse_dt(self, dt_str):
        if not dt_str or not dt_str.strip():
            return None
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def save_changes(self):
        if not self.selected_signin_id:
            return

        in_time_str = self.query_one("#edit_in_time").value
        out_time_str = self.query_one("#edit_out_time").value

        in_dt = self.parse_dt(in_time_str)
        out_dt = self.parse_dt(out_time_str)

        if not in_dt:
            self.app.notify("Invalid Sign In Time Format", severity="error")
            return

        try:
            with Session(engine) as session:
                att = session.get(models.SpaceAttendance, self.selected_signin_id)
                if att:
                    att.sign_in_time = in_dt
                    att.sign_out_time = out_dt
                    vtype_val = self.query_one("#edit_visit_type").value
                    att.visit_type = vtype_val if vtype_val != Select.BLANK else None
                    session.add(att)
                    session.commit()
                    self.app.notify("Sign In Updated")
                    self.load_data()
                else:
                    self.app.notify("Error: Record not found", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")

    def delete_entry(self):
        if not self.selected_signin_id:
            return

        try:
            with Session(engine) as session:
                att = session.get(models.SpaceAttendance, self.selected_signin_id)
                if att:
                    session.delete(att)
                    session.commit()
                    self.app.notify("Sign In Deleted")
                    self.load_data()

                    # Reset Form
                    self.query_one("#edit_in_time").value = ""
                    self.query_one("#edit_out_time").value = ""
                    self.query_one("#btn_save").disabled = True
                    self.query_one("#btn_delete").disabled = True
                    self.selected_signin_id = None
                else:
                    self.app.notify("Error: Record not found", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")

    def add_new_entry(self):
        in_time_str = self.query_one("#edit_in_time").value
        out_time_str = self.query_one("#edit_out_time").value

        # If empty, default to now for In-Time
        if not in_time_str:
            in_dt = datetime.now()
        else:
            in_dt = self.parse_dt(in_time_str)

        out_dt = self.parse_dt(out_time_str)

        if not in_dt:
            self.app.notify("Invalid Sign In Time Format", severity="error")
            return

        try:
            with Session(engine) as session:
                vtype_val = self.query_one("#edit_visit_type").value
                new_att = models.SpaceAttendance(
                    user_account_number=self.user_id,
                    sign_in_time=in_dt,
                    sign_out_time=out_dt,
                    visit_type=vtype_val if vtype_val != Select.BLANK else None,
                )
                session.add(new_att)
                session.commit()
                self.app.notify("New Sign In Added")
                self.load_data()

                # Reset Form logic optional, or keep for rapid entry
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")
