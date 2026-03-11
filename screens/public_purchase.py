"""
Public purchase modal for unauthenticated kiosk use.

Provides the same Manual Transaction form as the Purchases tab so staff or
walk-in visitors can process a payment without logging in. The transaction
history table deliberately omits customer name, email, and phone to protect
visitor privacy at a shared kiosk — amounts, descriptions, and statuses are
still shown for quick confirmation that a submission was recorded.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label

from core import square_service


class PublicPurchaseModal(ModalScreen):
    """
    Walk-in payment form accessible from the login screen without requiring a
    member account. Supports Square Terminal checkout and cash recording.
    The recent transaction table shows no customer-identifying information.
    """

    def compose(self) -> ComposeResult:
        pos_cfg = square_service.get_pos_config()
        pos_btn_label = (
            "Send to Square Terminal"
            if pos_cfg.square_enabled
            else "Record Transaction"
        )

        with Vertical(classes="splash-container"):
            yield Label("Manual Purchase", classes="title")
            with VerticalScroll(classes="splash-content"):
                yield Label("Amount ($):")
                yield Input(placeholder="0.00", id="pp_amount", type="number")

                yield Label("Customer Name:")
                yield Input(placeholder="First and Last Name", id="pp_customer_name")

                yield Label("Customer Email (optional):")
                yield Input(placeholder="customer@example.com", id="pp_customer_email")

                yield Label("Customer Phone (optional):")
                yield Input(placeholder="Phone number", id="pp_customer_phone")

                yield Label("Description:")
                yield Input(
                    placeholder="What is this transaction for?", id="pp_description"
                )

                with Horizontal(classes="filter-row"):
                    yield Button(
                        pos_btn_label,
                        variant="success",
                        id="btn_pp_process",
                    )
                    yield Button(
                        "Record Cash Transaction",
                        variant="warning",
                        id="btn_pp_cash",
                    )
                    yield Button("Clear", id="btn_pp_clear")

                yield Label("Recent Transactions:", classes="subtitle")
                # Customer columns are intentionally omitted here — this table
                # is visible on a shared login screen where other visitors may
                # see it, so only non-identifying fields are displayed.
                yield DataTable(id="pp_txns_table")

                yield Button("Refresh", id="btn_pp_refresh")

            with Horizontal(classes="filter-row"):
                yield Button("Close", variant="error", id="btn_pp_close")

    def on_mount(self):
        table = self.query_one("#pp_txns_table", DataTable)
        table.add_columns("ID", "Date", "Amount", "Description", "Status", "Via")
        self._load_transactions()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_pp_process":
            self._process_transaction()
        elif event.button.id == "btn_pp_cash":
            self._record_cash()
        elif event.button.id == "btn_pp_clear":
            self._clear_form()
        elif event.button.id == "btn_pp_refresh":
            self._load_transactions()
        elif event.button.id == "btn_pp_close":
            self.dismiss()

    def _load_transactions(self):
        """Populates the table with recent transactions, hiding customer details."""
        table = self.query_one("#pp_txns_table", DataTable)
        table.clear()
        transactions = square_service.get_recent_transactions(limit=20)
        for txn in transactions:
            # Determine the "Via" display based on payment method and status
            if txn.square_status == "cash_square":
                via = "Cash (Square)"
            elif txn.square_status == "cash":
                via = "Cash"
            elif txn.is_local:
                via = "Local"
            else:
                via = "Square"
            table.add_row(
                str(txn.id),
                txn.created_at.strftime("%Y-%m-%d %H:%M"),
                f"${txn.amount:.2f}",
                txn.description or "",
                txn.square_status,
                via,
            )

    def _read_form(self):
        """
        Reads and validates form inputs. Returns a dict of values on success
        or None if validation fails (notification already shown to the user).
        """
        amount_str = self.query_one("#pp_amount", Input).value.strip()
        customer_name = self.query_one("#pp_customer_name", Input).value.strip()
        customer_email = self.query_one("#pp_customer_email", Input).value.strip()
        customer_phone = self.query_one("#pp_customer_phone", Input).value.strip()
        description = self.query_one("#pp_description", Input).value.strip()

        if not amount_str:
            self.app.notify("Amount is required.", severity="error")
            return None
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            self.app.notify("Amount must be a positive number.", severity="error")
            return None
        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return None

        return {
            "amount": amount,
            "customer_name": customer_name,
            "customer_email": customer_email or None,
            "customer_phone": customer_phone or None,
            "description": description or None,
        }

    def _process_transaction(self):
        """Sends a Square Terminal checkout or records a local transaction."""
        form = self._read_form()
        if form is None:
            return

        ok, message, txn = square_service.process_terminal_checkout(
            amount=form["amount"],
            customer_name=form["customer_name"],
            customer_email=form["customer_email"],
            customer_phone=form["customer_phone"],
            description=form["description"],
        )
        self.app.notify(message, severity="information" if ok else "error")
        if txn:
            self._clear_form()
            self._load_transactions()

    def _record_cash(self):
        """Records a cash payment either to Square (if enabled) or locally."""
        form = self._read_form()
        if form is None:
            return

        ok, message, txn = square_service.record_cash_payment(
            amount=form["amount"],
            customer_name=form["customer_name"],
            customer_email=form["customer_email"],
            customer_phone=form["customer_phone"],
            description=form["description"],
        )
        self.app.notify(message, severity="information" if ok else "error")
        if txn:
            self._clear_form()
            self._load_transactions()

    def _clear_form(self):
        """Resets all form inputs to empty."""
        for field_id in (
            "pp_amount",
            "pp_customer_name",
            "pp_customer_email",
            "pp_customer_phone",
            "pp_description",
        ):
            self.query_one(f"#{field_id}", Input).value = ""
