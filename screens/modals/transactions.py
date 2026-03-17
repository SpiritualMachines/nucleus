"""Transaction and credit balance modals for the dashboard."""

__all__ = [
    "TransactionModal",
    "ViewCreditsModal",
]

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label

from core import services, square_service


class TransactionModal(ModalScreen):
    def __init__(self, user_id: int, initial_type="credit", currency_name="Credits"):
        super().__init__()
        self.user_id = user_id
        self.initial_type = initial_type
        self.currency_name = currency_name
        # Load current balance so staff can see it before adjusting
        self.current_balance = services.get_user_balance(user_id)
        # Load POS config only for credit type (payment processing)
        self.square_enabled = False
        if initial_type == "credit":
            pos_cfg = square_service.get_pos_config()
            self.square_enabled = pos_cfg.square_enabled

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container scrollable"):
            if self.initial_type == "credit":
                yield Label(f"Add {self.currency_name}", classes="title")
            else:
                yield Label(f"Deduct {self.currency_name}", classes="title")

            yield Label(
                f"Current Balance: ${self.current_balance:.2f}",
                classes="subtitle",
            )

            yield Label("Amount ($):")
            yield Input(placeholder="0.00", type="number", id="txn_amount")

            yield Label("Description:")
            yield Input(placeholder="e.g., 3D Print Filament", id="txn_desc")

            with Horizontal(classes="filter-row"):
                if self.initial_type == "credit":
                    # For credit: show payment buttons
                    square_label = (
                        "Process Square Transaction"
                        if self.square_enabled
                        else "Process Transaction (Local)"
                    )
                    yield Button(square_label, variant="success", id="btn_pay_square")
                    yield Button("Record as Cash", variant="warning", id="btn_pay_cash")
                else:
                    # For debit: show single record button
                    yield Button(
                        f"Record {self.currency_name} Deduction",
                        variant="primary",
                        id="btn_process",
                    )
            with Horizontal(classes="filter-row"):
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_process":
            # Debit: single record button
            self.process_txn(None)
        elif event.button.id == "btn_pay_square":
            # Credit: Square payment
            self.process_txn("square")
        elif event.button.id == "btn_pay_cash":
            # Credit: Cash payment
            self.process_txn("cash")

    def process_txn(self, payment_method: str | None):
        """Process transaction with optional payment processing.

        Args:
            payment_method: "square", "cash", or None (for debit-only)
        """
        try:
            amt_str = self.query_one("#txn_amount").value
            amount = float(amt_str)
            desc = self.query_one("#txn_desc").value

            # Record the transaction in the database
            services.add_transaction(self.user_id, amount, self.initial_type, desc)

            # If credit type with payment method, process payment
            if self.initial_type == "credit" and amount > 0 and payment_method:
                user = services.get_user_by_account(self.user_id)
                customer_name = f"{user.first_name} {user.last_name}"
                customer_email = user.email

                if payment_method == "square":
                    # Process with Square
                    try:
                        square_service.process_terminal_checkout(
                            amount=amount,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            customer_phone=None,
                            description=desc,
                        )
                        self.app.notify(f"{self.currency_name} Added via Square")
                    except Exception as e:
                        self.app.notify(f"Square Error: {str(e)}", severity="error")
                elif payment_method == "cash":
                    # Record cash payment
                    try:
                        square_service.record_cash_payment(
                            amount=amount,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            customer_phone=None,
                            description=desc,
                        )
                        self.app.notify(f"{self.currency_name} Added via Cash")
                    except Exception as e:
                        self.app.notify(
                            f"Cash Recording Error: {str(e)}", severity="error"
                        )
            elif self.initial_type == "credit" and amount == 0:
                self.app.notify("No payment recorded (zero amount)")
            elif self.initial_type == "debit":
                self.app.notify(f"{self.currency_name} Deducted")
            else:
                self.app.notify(f"{self.currency_name} Recorded")

            self.dismiss(True)
        except ValueError:
            self.app.notify("Invalid Amount", severity="error")


class ViewCreditsModal(ModalScreen):
    """Read-only view of a user's current credit balance and full transaction history."""

    def __init__(self, user_id: int, currency_name: str = "Credits"):
        super().__init__()
        self.user_id = user_id
        self.currency_name = currency_name
        self.balance = services.get_user_balance(user_id)
        self.transactions = services.get_user_transactions(user_id)

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label(f"{self.currency_name} Balance", classes="title")
            yield Label(
                f"Current Balance: ${self.balance:.2f}",
                classes="subtitle",
                id="balance_display",
            )
            yield Label("Transaction History:", classes="subtitle")
            yield DataTable(id="credits_history_table")
            with Horizontal(classes="filter-row"):
                yield Button("Close", id="btn_close")

    def on_mount(self) -> None:
        table = self.query_one("#credits_history_table", DataTable)
        table.add_columns("Date", "Type", "Amount", "Description")
        for txn in self.transactions:
            table.add_row(
                txn.date.strftime("%Y-%m-%d %H:%M"),
                txn.credit_debit.capitalize(),
                f"${txn.credits:.2f}",
                txn.description or "",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close":
            self.dismiss()
