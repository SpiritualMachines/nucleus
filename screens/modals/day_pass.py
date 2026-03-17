"""Day pass modals for the dashboard."""

__all__ = [
    "AddDayPassModal",
    "DayPassHistoryModal",
]

from datetime import datetime

from sqlmodel import Session
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select

from core import models, services, square_service
from core.database import engine


class AddDayPassModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        pos_cfg = square_service.get_pos_config()
        self.square_enabled = pos_cfg.square_enabled
        # Load all active day pass tiers for the optional tier selector
        self._tiers = services.get_product_tiers("daypass")

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container scrollable"):
            yield Label("Add Day Pass", classes="title")

            yield Label("Day Pass Tier (optional):")
            tier_options = [("Custom", "0")] + [
                (t.name, str(t.id)) for t in self._tiers
            ]
            yield Select(tier_options, id="dp_tier_select", value="0")

            yield Label("Date (YYYY-MM-DD):")
            yield Input(datetime.now().strftime("%Y-%m-%d"), id="dp_date")

            yield Checkbox("Borrowed NBP Library Day Pass", id="chk_nbp_library")

            yield Label("Description:")
            yield Input("Day Pass", id="dp_desc")

            yield Label("Amount ($) (optional):")
            yield Input(placeholder="0.00", type="number", id="dp_amount")

            with Horizontal(classes="filter-row"):
                square_label = (
                    "Process Square Transaction"
                    if self.square_enabled
                    else "Process Transaction (Local)"
                )
                yield Button(square_label, variant="success", id="btn_pay_square")
                yield Button("Record as Cash", variant="warning", id="btn_pay_cash")
            with Horizontal(classes="filter-row"):
                yield Button("Cancel", id="btn_cancel")

    def on_select_changed(self, event: Select.Changed):
        """Auto-fill description and amount when a day pass tier is selected."""
        if event.select.id != "dp_tier_select":
            return
        if event.value == "0" or event.value is Select.BLANK:
            return
        tier = services.get_product_tier(int(event.value))
        if not tier:
            return
        self.query_one("#dp_desc", Input).value = tier.name
        self.query_one("#dp_amount", Input).value = str(tier.price)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_pay_square":
            self._save_day_pass("square")
        elif event.button.id == "btn_pay_cash":
            self._save_day_pass("cash")

    def _save_day_pass(self, payment_method: str):
        """Save day pass and process payment if amount provided.

        Args:
            payment_method: "square" or "cash"
        """
        try:
            date_str = self.query_one("#dp_date").value
            desc = self.query_one("#dp_desc").value
            amount_str = self.query_one("#dp_amount").value

            if self.query_one("#chk_nbp_library").value:
                desc = f"[NBP-Library] {desc}"

            dt = datetime.strptime(date_str, "%Y-%m-%d")
            amount = float(amount_str) if amount_str else 0.0

            # Create the day pass record
            services.add_day_pass(self.user_id, dt, desc)

            # Process payment if amount > 0
            if amount > 0:
                user_obj = services.get_user_by_account(self.user_id)
                customer_name = f"{user_obj.first_name} {user_obj.last_name}"
                customer_email = user_obj.email

                if payment_method == "square":
                    try:
                        square_service.process_terminal_checkout(
                            amount=amount,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            customer_phone=None,
                            description=desc,
                        )
                        self.app.notify("Day Pass Added - Square payment processed")
                    except Exception as e:
                        self.app.notify(f"Square Error: {str(e)}", severity="error")
                elif payment_method == "cash":
                    try:
                        square_service.record_cash_payment(
                            amount=amount,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            customer_phone=None,
                            description=desc,
                        )
                        self.app.notify("Day Pass Added - Cash payment recorded")
                    except Exception as e:
                        self.app.notify(
                            f"Cash Recording Error: {str(e)}", severity="error"
                        )
            else:
                self.app.notify("Day Pass Added - No payment recorded")

            self.dismiss(True)
        except ValueError:
            self.app.notify("Invalid Date or Amount", severity="error")


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
