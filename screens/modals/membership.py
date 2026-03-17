"""Membership management modals for the dashboard."""

__all__ = [
    "AddMembershipModal",
    "ManageMembershipsModal",
]

from datetime import datetime, timedelta

from sqlmodel import Session
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select

from core import models, services, square_service
from core.database import engine


class AddMembershipModal(ModalScreen):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        pos_cfg = square_service.get_pos_config()
        self.square_enabled = pos_cfg.square_enabled
        # Load all active membership tiers for the optional tier selector
        self._tiers = services.get_product_tiers("membership")
        # Holds the ID of the selected tier, or None when using Custom entry
        self._selected_tier_id = None

    def compose(self) -> ComposeResult:
        today = datetime.now()
        next_month = today + timedelta(days=30)
        current_month_name = today.strftime("%B")

        with Vertical(classes="splash-container scrollable"):
            yield Label("Add Membership", classes="title")

            yield Label("Membership Tier (optional):")
            tier_options = [("Custom", "0")] + [
                (t.name, str(t.id)) for t in self._tiers
            ]
            yield Select(tier_options, id="mem_tier_select", value="0")

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="mem_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(next_month.strftime("%Y-%m-%d"), id="mem_end")

            yield Label("Description / Month:")
            yield Input(current_month_name, id="mem_desc")

            yield Label("Amount ($) (optional):")
            yield Input(placeholder="0.00", type="number", id="mem_amount")

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
        """Auto-fill form fields when a tier is selected from the dropdown."""
        if event.select.id != "mem_tier_select":
            return
        if event.value == "0" or event.value is Select.BLANK:
            # Custom -- clear auto-filled marker but leave current values intact
            self._selected_tier_id = None
            return
        tier = services.get_product_tier(int(event.value))
        if not tier:
            return
        self._selected_tier_id = tier.id
        today = datetime.now()
        self.query_one("#mem_start", Input).value = today.strftime("%Y-%m-%d")
        if tier.duration_days:
            end_date = today + timedelta(days=tier.duration_days)
            self.query_one("#mem_end", Input).value = end_date.strftime("%Y-%m-%d")
        self.query_one("#mem_desc", Input).value = tier.name
        self.query_one("#mem_amount", Input).value = str(tier.price)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_pay_square":
            self._save_membership("square")
        elif event.button.id == "btn_pay_cash":
            self._save_membership("cash")

    def _save_membership(self, payment_method: str):
        """Save membership and process payment if amount provided.

        Args:
            payment_method: "square" or "cash"
        """
        try:
            start_str = self.query_one("#mem_start").value
            end_str = self.query_one("#mem_end").value
            desc_str = self.query_one("#mem_desc").value
            amount_str = self.query_one("#mem_amount").value

            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
            amount = float(amount_str) if amount_str else 0.0

            # Direct DB Insert to include Description
            with Session(engine) as session:
                # Update User Role
                user = session.get(models.User, self.user_id)
                if user:
                    user.role = models.UserRole.MEMBER
                    session.add(user)

                # Create Membership
                mem = models.ActiveMembership(
                    user_account_number=self.user_id,
                    start_date=start_date,
                    end_date=end_date,
                    description=desc_str,
                )
                try:
                    mem.description = desc_str
                except Exception:
                    pass

                session.add(mem)
                session.commit()

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
                            description=f"Membership: {desc_str}",
                        )
                        self.app.notify(
                            f"Added membership ({desc_str}) - Square payment processed"
                        )
                    except Exception as e:
                        self.app.notify(f"Square Error: {str(e)}", severity="error")
                elif payment_method == "cash":
                    try:
                        square_service.record_cash_payment(
                            amount=amount,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            customer_phone=None,
                            description=f"Membership: {desc_str}",
                        )
                        self.app.notify(
                            f"Added membership ({desc_str}) - Cash payment recorded"
                        )
                    except Exception as e:
                        self.app.notify(
                            f"Cash Recording Error: {str(e)}", severity="error"
                        )
            else:
                self.app.notify(f"Added membership ({desc_str}) - No payment recorded")

            # Apply consumables credits bundled with the selected tier, if any
            if self._selected_tier_id is not None:
                tier = services.get_product_tier(self._selected_tier_id)
                if tier and tier.consumables_credits and tier.consumables_credits > 0:
                    services.add_transaction(
                        self.user_id,
                        tier.consumables_credits,
                        "credit",
                        f"Consumables credits included with {tier.name}",
                    )

            self.dismiss(True)
        except ValueError:
            self.app.notify("Invalid Date Format or Amount", severity="error")
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
