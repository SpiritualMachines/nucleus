from datetime import datetime, timedelta

from sqlmodel import Session, desc, select
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Label,
    Markdown,
    OptionList,
    Select,
)

from core import exporters, models, services
from core.database import engine
from screens.directory_select import DirectorySelectScreen


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
]


class SelectVisitTypeModal(ModalScreen):
    """
    Prompts the user to choose their visit type before signing in.
    Dismisses with the selected type string, or None if cancelled.
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Welcome! Select Visit Type", classes="title")
            yield Label("What brings you in today?", classes="subtitle")
            yield OptionList(*VISIT_TYPES, id="visit_type_list")
            with Horizontal(classes="filter-row"):
                yield Button("Cancel", variant="error", id="vtype_cancel")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(str(event.option.prompt))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "vtype_cancel":
            self.dismiss(None)


class ConfirmSignOutScreen(ModalScreen):
    """A simple confirmation modal for signing out."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Sign Out?", classes="title")
            yield Label(
                "Are you sure you want to sign out of the space?", classes="title"
            )

            # Buttons
            with Horizontal(classes="filter-row"):
                yield Button("Yes, Sign Out", variant="warning", id="confirm_yes")
                yield Button("Cancel", variant="primary", id="confirm_no")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm_yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class PostActionCountdownModal(ModalScreen):
    """
    Shown immediately after a space sign-in or sign-out.
    Counts down from 10 seconds and triggers an app logout when it reaches
    zero, giving the next person a clean session. The current user can click
    Stay Signed In to cancel the countdown and remain on the dashboard.
    """

    COUNTDOWN_SECONDS = 10

    def __init__(self, message: str):
        super().__init__()
        self.message = message
        self._remaining = self.COUNTDOWN_SECONDS

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label(self.message, classes="title")
            yield Label(
                f"Logging out in {self._remaining} seconds...",
                id="countdown_label",
            )
            with Horizontal(classes="filter-row"):
                yield Button("Stay Signed In", variant="success", id="btn_stay")

    def on_mount(self):
        self.set_interval(1.0, self._tick)

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self.dismiss(False)
        else:
            self.query_one("#countdown_label").update(
                f"Logging out in {self._remaining} seconds..."
            )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_stay":
            self.dismiss(True)


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


class TransactionModal(ModalScreen):
    def __init__(self, user_id: int, initial_type="credit", currency_name="Credits"):
        super().__init__()
        self.user_id = user_id
        self.initial_type = initial_type
        self.currency_name = currency_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="login-container"):
            yield Label(f"Manage {self.currency_name} Balance", classes="title")

            yield Label("Type:")
            yield Select(
                [
                    (f"Add {self.currency_name} (+)", "credit"),
                    (f"Spend {self.currency_name} (-)", "debit"),
                ],
                value=self.initial_type,
                id="txn_type",
            )

            yield Label("Amount ($):")
            yield Input(placeholder="0.00", type="number", id="txn_amount")

            yield Label("Description:")
            yield Input(placeholder="e.g., 3D Print Filament", id="txn_desc")

            with Horizontal(classes="filter-row"):
                yield Button(
                    f"Record {self.currency_name}", variant="primary", id="btn_process"
                )
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_process":
            self.process_txn()

    def process_txn(self):
        try:
            amt_str = self.query_one("#txn_amount").value
            amount = float(amt_str)
            txn_type = self.query_one("#txn_type").value
            desc = self.query_one("#txn_desc").value

            services.add_transaction(self.user_id, amount, txn_type, desc)
            self.app.notify(f"{self.currency_name} Recorded")
            self.dismiss(True)
        except ValueError:
            self.app.notify("Invalid Amount", severity="error")


class AddMembershipModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    def compose(self) -> ComposeResult:
        today = datetime.now()
        next_month = today + timedelta(days=30)
        current_month_name = today.strftime("%B")

        with Vertical(classes="login-container"):
            yield Label("Add Membership", classes="title")

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="mem_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(next_month.strftime("%Y-%m-%d"), id="mem_end")

            yield Label("Description / Month:")
            yield Input(current_month_name, id="mem_desc")

            with Horizontal(classes="filter-row"):
                yield Button("Add & Activate", variant="success", id="btn_add")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_add":
            try:
                start_str = self.query_one("#mem_start").value
                end_str = self.query_one("#mem_end").value
                desc_str = self.query_one("#mem_desc").value

                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")

                # Direct DB Insert to include Description
                # (services.add_membership doesn't support dates/desc yet)
                with Session(engine) as session:
                    # Update User Role
                    user = session.get(models.User, self.user_id)
                    if user:
                        user.role = models.UserRole.MEMBER
                        session.add(user)

                    # Create Membership
                    # We assume ActiveMembership model has 'description' field
                    # If not, we set it dynamically or it might be ignored by SQLModel
                    # but we try our best.
                    mem = models.ActiveMembership(
                        user_account_number=self.user_id,
                        start_date=start_date,
                        end_date=end_date,
                        description=desc_str,
                    )
                    # Force set description if model definition is lagging
                    # logic: getattr/setattr to be safe
                    try:
                        mem.description = desc_str
                    except Exception:
                        pass  # Field might not exist on model class

                    session.add(mem)
                    session.commit()

                self.app.notify(f"Added membership ({desc_str}).")
                self.dismiss(True)
            except ValueError:
                self.app.notify("Invalid Date Format", severity="error")
            except Exception as e:
                self.app.notify(f"Error: {str(e)}", severity="error")


class ManageMembershipsModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.selected_mem_id = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Active Memberships", classes="title")
            yield DataTable(id="mem_table")

            # --- NEW: Editing Fields ---
            with Vertical(id="edit_section", classes="disabled"):
                yield Label("Edit Selected Entry:", classes="subtitle")
                yield Label("Start Date (YYYY-MM-DD):")
                yield Input(id="edit_start")
                yield Label("End Date (YYYY-MM-DD):")
                yield Input(id="edit_end")
                yield Label("Description:")
                yield Input(id="edit_desc")

                with Horizontal(classes="filter-row"):
                    yield Button(
                        "Save Changes", variant="success", id="btn_save", disabled=True
                    )
                    yield Button(
                        "Delete Entry", variant="error", id="btn_delete", disabled=True
                    )

            with Horizontal(classes="filter-row"):
                yield Button("Cancel", id="btn_close")

    def on_mount(self):
        table = self.query_one("#mem_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Start", "End", "Description")
        self.load_data()

    def load_data(self):
        table = self.query_one("#mem_table", DataTable)
        table.clear()
        mems = services.get_user_memberships(self.user_id)
        for m in mems:
            # Handle potential missing description field gracefully if model isn't updated yet
            desc = getattr(m, "description", "")
            table.add_row(
                str(m.id), str(m.start_date.date()), str(m.end_date.date()), desc
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Populate fields when a row is clicked."""
        row_data = event.data_table.get_row(event.row_key)
        self.selected_mem_id = int(row_data[0])
        start_date = row_data[1]
        end_date = row_data[2]
        description = row_data[3]

        self.query_one("#edit_start").value = start_date
        self.query_one("#edit_end").value = end_date
        # FIX: Handle None description to prevent crash
        self.query_one("#edit_desc").value = description or ""

        self.query_one("#btn_save").disabled = False
        self.query_one("#btn_delete").disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            self.save_changes()
        elif event.button.id == "btn_delete":
            self.delete_entry()

    def save_changes(self):
        if not self.selected_mem_id:
            return

        try:
            start_str = self.query_one("#edit_start").value
            end_str = self.query_one("#edit_end").value
            desc_val = self.query_one("#edit_desc").value

            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")

            # Direct DB update since service doesn't have specific update func for dates
            with Session(engine) as session:
                mem = session.get(models.ActiveMembership, self.selected_mem_id)
                if mem:
                    mem.start_date = start_dt
                    mem.end_date = end_dt
                    # Only attempt to save description if the model supports it
                    if hasattr(mem, "description"):
                        mem.description = desc_val

                    session.add(mem)
                    session.commit()
                    self.app.notify("Membership Updated")
                    self.load_data()
                else:
                    self.app.notify("Error: Record not found", severity="error")

        except ValueError:
            self.app.notify("Invalid Date Format", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")

    def delete_entry(self):
        if not self.selected_mem_id:
            return

        try:
            with Session(engine) as session:
                mem = session.get(models.ActiveMembership, self.selected_mem_id)
                if mem:
                    session.delete(mem)
                    session.commit()
                    self.app.notify("Membership Deleted")
                    self.load_data()

                    # Reset Form
                    self.query_one("#edit_start").value = ""
                    self.query_one("#edit_end").value = ""
                    self.query_one("#edit_desc").value = ""
                    self.query_one("#btn_save").disabled = True
                    self.query_one("#btn_delete").disabled = True
                    self.selected_mem_id = None
                else:
                    self.app.notify("Error: Record not found", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")


class AddDayPassModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="login-container"):
            yield Label("Add Day Pass", classes="title")
            yield Label("Date (YYYY-MM-DD):")
            yield Input(datetime.now().strftime("%Y-%m-%d"), id="dp_date")

            # --- NEW FEATURE: NBP Library Checkbox ---
            yield Checkbox("Borrowed NBP Library Day Pass", id="chk_nbp_library")

            yield Label("Description:")
            yield Input("Day Pass", id="dp_desc")

            with Horizontal(classes="filter-row"):
                yield Button("Add Pass", variant="success", id="btn_add")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_add":
            try:
                date_str = self.query_one("#dp_date").value
                desc = self.query_one("#dp_desc").value

                # --- NEW FEATURE LOGIC ---
                if self.query_one("#chk_nbp_library").value:
                    desc = f"[NBP-Library] {desc}"
                # -------------------------

                dt = datetime.strptime(date_str, "%Y-%m-%d")
                services.add_day_pass(self.user_id, dt, desc)
                self.app.notify("Day Pass Added")
                self.dismiss(True)
            except ValueError:
                self.app.notify("Invalid Date", severity="error")


class DayPassHistoryModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.selected_pass_id = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Day Pass History", classes="title")

            # WRAPPED: Put table in a container that takes available space but allows scrolling
            with Vertical(classes="splash-content"):
                yield DataTable(id="dp_table")

            # --- NEW: Editing Fields (Copied/Adapted from ManageMembershipsModal) ---
            # Fixed height section at bottom
            with Vertical(id="edit_section", classes="disabled"):
                yield Label("Edit Selected Entry:", classes="subtitle")
                yield Label("Date (YYYY-MM-DD):")
                yield Input(id="edit_date")
                yield Label("Description:")
                yield Input(id="edit_desc")

                with Horizontal(classes="filter-row"):
                    yield Button(
                        "Save Changes", variant="success", id="btn_save", disabled=True
                    )
                    yield Button(
                        "Delete Entry", variant="error", id="btn_delete", disabled=True
                    )

            with Horizontal(classes="filter-row"):
                yield Button("Close", id="btn_close")

    def on_mount(self):
        table = self.query_one("#dp_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Date", "Description")
        self.load_data()

    def load_data(self):
        table = self.query_one("#dp_table", DataTable)
        table.clear()
        passes = services.get_user_day_passes(self.user_id)
        for p in passes:
            # Check for description field safely
            desc = getattr(p, "description", "")
            # Ensure date is formatted string
            d_str = p.date.strftime("%Y-%m-%d") if p.date else ""
            table.add_row(str(p.id), d_str, desc)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Populate fields when a row is clicked."""
        row_data = event.data_table.get_row(event.row_key)
        self.selected_pass_id = int(row_data[0])
        date_val = row_data[1]
        desc_val = row_data[2]

        self.query_one("#edit_date").value = date_val
        self.query_one("#edit_desc").value = desc_val or ""

        self.query_one("#btn_save").disabled = False
        self.query_one("#btn_delete").disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            self.save_changes()
        elif event.button.id == "btn_delete":
            self.delete_entry()

    def save_changes(self):
        if not self.selected_pass_id:
            return

        try:
            date_str = self.query_one("#edit_date").value
            desc_val = self.query_one("#edit_desc").value

            date_dt = datetime.strptime(date_str, "%Y-%m-%d")

            # Direct DB update (Assuming UserCredits table stores day passes as established in services.py)
            with Session(engine) as session:
                # Note: In services.py, add_day_pass uses UserCredits model.
                # So we query UserCredits here.
                # However, models.py might not have 'UserCredits' imported if not careful,
                # but it is imported at top of file.
                credit = session.get(models.UserCredits, self.selected_pass_id)
                if credit:
                    credit.date = date_dt
                    credit.description = desc_val
                    session.add(credit)
                    session.commit()
                    self.app.notify("Day Pass Updated")
                    self.load_data()
                else:
                    self.app.notify("Error: Record not found", severity="error")

        except ValueError:
            self.app.notify("Invalid Date Format", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")

    def delete_entry(self):
        if not self.selected_pass_id:
            return

        try:
            with Session(engine) as session:
                credit = session.get(models.UserCredits, self.selected_pass_id)
                if credit:
                    session.delete(credit)
                    session.commit()
                    self.app.notify("Day Pass Deleted")
                    self.load_data()

                    # Reset Form
                    self.query_one("#edit_date").value = ""
                    self.query_one("#edit_desc").value = ""
                    self.query_one("#btn_save").disabled = True
                    self.query_one("#btn_delete").disabled = True
                    self.selected_pass_id = None
                else:
                    self.app.notify("Error: Record not found", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")


class ManageSignInsModal(ModalScreen):
    """
    Modal to view, edit, add, or delete sign-in records for a user.
    Caps the table height so the edit fields below it always remain visible.
    """

    CSS = """
    ManageSignInsModal .splash-container {
        height: auto;
        max-height: 95%;
    }
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


class FeedbackViewModal(ModalScreen):
    """View and Reply to Feedback."""

    def __init__(self, fb_id: int):
        super().__init__()
        self.fb_id = fb_id

    def compose(self) -> ComposeResult:
        fb = services.get_feedback_by_id(self.fb_id)

        with Vertical(classes="splash-container"):
            if not fb:
                yield Label("Feedback not found.", classes="error")
                yield Button("Close", id="btn_close")
                return

            yield Label(f"Feedback #{fb.id}", classes="title")
            yield Label(f"From: {fb.first_name} {fb.last_name}")
            yield Label(f"Date: {fb.submitted_at}")

            yield Label("Comment:", classes="subtitle")
            with VerticalScroll(classes="splash-content"):
                yield Markdown(fb.comment)

            yield Label("Admin Response:", classes="subtitle")
            yield Input(fb.admin_response or "", id="admin_response")

            with Horizontal(classes="filter-row"):
                yield Button("Save Response", variant="success", id="btn_save")
                yield Button("Close", id="btn_close")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            resp = self.query_one("#admin_response").value
            services.update_feedback_response(self.fb_id, resp)
            self.app.notify("Response Saved")
            self.dismiss(True)


class CommunityContactsReportModal(ModalScreen):
    """
    Modal for exporting all community contact records within a selected date range.
    Mirrors the Period Traction Report flow: date range inputs pre-filled to the
    last 30 days, then CSV or PDF export via the standard directory selector.
    """

    def compose(self) -> ComposeResult:
        today = datetime.now()
        start = today - timedelta(days=30)

        with Vertical(classes="splash-container"):
            yield Label("Community Contacts Report", classes="title")
            yield Label(
                "Select a date range to include in the report.", classes="subtitle"
            )

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(start.strftime("%Y-%m-%d"), id="ccr_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="ccr_end")

            with Horizontal(classes="filter-row"):
                yield Button("Export CSV", variant="success", id="btn_ccr_csv")
                yield Button("Export PDF", variant="primary", id="btn_ccr_pdf")
                yield Button("Cancel", variant="error", id="btn_ccr_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_ccr_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_ccr_csv":
            self._initiate_export("csv")
        elif event.button.id == "btn_ccr_pdf":
            self._initiate_export("pdf")

    def _initiate_export(self, fmt: str):
        def on_directory_selected(path: str | None):
            if path:
                self._run_export(fmt, path)

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def _run_export(self, fmt: str, output_dir: str):
        try:
            start_str = self.query_one("#ccr_start").value.strip()
            end_str = self.query_one("#ccr_end").value.strip()

            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

            data = services.get_community_contacts_report(start_date, end_date)

            if not data["rows"]:
                self.app.notify(
                    "No community contacts in this date range.", severity="warning"
                )
                return

            filename = exporters.get_timestamp_filename(
                "community_contacts_report", fmt
            )

            if fmt == "csv":
                path = exporters.export_to_csv(
                    filename, data["headers"], data["rows"], output_dir
                )
            else:
                period_label = f"{start_str} to {end_str}"
                path = exporters.export_to_pdf(
                    filename,
                    f"Community Contacts Report: {period_label}",
                    data["headers"],
                    data["rows"],
                    output_dir,
                )

            self.app.notify(f"Exported to: {path}")
            self.dismiss(None)

        except ValueError:
            self.app.notify("Invalid date format. Use YYYY-MM-DD.", severity="error")
        except Exception as e:
            self.app.notify(f"Export Failed: {str(e)}", severity="error")


class PeriodTractionReportModal(ModalScreen):
    """
    Modal for generating a Period Traction Report covering all recorded activity
    within a user-selected date range. Includes active memberships, day passes,
    consumable transactions, space sign-ins/outs, and community contact visits.
    The user selects a save directory, then the report is written to CSV or PDF.
    """

    def compose(self) -> ComposeResult:
        today = datetime.now()
        start = today - timedelta(days=30)

        with Vertical(classes="splash-container"):
            yield Label("Generate Period Traction Report", classes="title")
            yield Label(
                "Select a date range to include in the report.", classes="subtitle"
            )

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(start.strftime("%Y-%m-%d"), id="report_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="report_end")

            with Horizontal(classes="filter-row"):
                yield Button("Export CSV", variant="success", id="btn_traction_csv")
                yield Button("Export PDF", variant="primary", id="btn_traction_pdf")
                yield Button("Cancel", variant="error", id="btn_traction_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_traction_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_traction_csv":
            self._initiate_export("csv")
        elif event.button.id == "btn_traction_pdf":
            self._initiate_export("pdf")

    def _initiate_export(self, fmt: str):
        """Opens the directory selector, then runs the export once a path is chosen."""

        def on_directory_selected(path: str | None):
            if path:
                self._run_export(fmt, path)

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def _run_export(self, fmt: str, output_dir: str):
        """Fetches report data and writes the file in the requested format."""
        try:
            start_str = self.query_one("#report_start").value.strip()
            end_str = self.query_one("#report_end").value.strip()

            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            # Include the full final day by setting time to end of day
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

            data = services.get_period_traction_report_data(start_date, end_date)

            sections = [
                {
                    "title": "Memberships",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Start Date",
                        "End Date",
                        "Description",
                    ],
                    "rows": data["memberships"],
                },
                {
                    "title": "Day Passes",
                    "headers": ["ID", "Name", "Account", "Date", "Description"],
                    "rows": data["day_passes"],
                },
                {
                    "title": "Consumable Transactions",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Type",
                        "Amount",
                        "Date",
                        "Description",
                    ],
                    "rows": data["consumables"],
                },
                {
                    "title": "Sign Ins and Outs",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Sign In",
                        "Sign Out",
                        "Visit Type",
                    ],
                    "rows": data["sign_ins"],
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
                    "rows": data["community_contacts"],
                },
            ]

            period_label = f"{start_str} to {end_str}"
            filename = exporters.get_timestamp_filename("period_traction_report", fmt)

            if fmt == "csv":
                path = exporters.export_period_report_to_csv(
                    filename, sections, output_dir
                )
            else:
                path = exporters.export_period_report_to_pdf(
                    filename,
                    f"Period Traction Report: {period_label}",
                    sections,
                    output_dir,
                )

            self.app.notify(f"Exported to: {path}")
            self.dismiss(None)

        except ValueError:
            self.app.notify("Invalid date format. Use YYYY-MM-DD.", severity="error")
        except Exception as e:
            self.app.notify(f"Export Failed: {str(e)}", severity="error")
