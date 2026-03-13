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

from core import services, square_service


class PublicPurchaseModal(ModalScreen):
    """
    Walk-in payment form accessible from the login screen without requiring a
    member account. Supports Square Terminal checkout and cash recording.
    Includes the inventory cart so staff can build a transaction from preset
    items rather than typing amounts and descriptions manually.
    The recent transaction table shows no customer-identifying information.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Per-instance cart state — list of {id, name, qty, unit_price}
        self._cart: list = []
        self._inv_selected_item: dict = None
        self._inv_selected_cart_item_id: int = None

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

                # Step 1: Inventory Cart
                with Vertical(classes="form-subsection"):
                    yield Label("Step 1: Select Items (Optional)", classes="subtitle")
                    yield Label(
                        "Click an item row to select it, set the quantity,"
                        " then click Add to Cart."
                        " Amount and Description are auto-filled."
                    )
                    yield DataTable(id="pp_inv_available_table")
                    with Horizontal(classes="filter-row"):
                        yield Label("Quantity:")
                        yield Input("1", id="pp_inv_qty", type="number")
                        yield Button(
                            "Add to Cart", variant="primary", id="btn_pp_add_to_cart"
                        )
                    yield Label("Cart:", classes="subtitle")
                    yield DataTable(id="pp_inv_cart_table")
                    with Horizontal(classes="filter-row"):
                        yield Label("Cart Total: $0.00", id="pp_inv_cart_total_lbl")
                        yield Button(
                            "Remove Selected",
                            variant="error",
                            id="btn_pp_remove_from_cart",
                            disabled=True,
                        )
                        yield Button("Clear Cart", id="btn_pp_clear_cart")

                # Step 2: Transaction Details
                with Vertical(classes="form-subsection"):
                    yield Label("Step 2: Transaction Details", classes="subtitle")
                    yield Label(
                        "Auto-filled from cart. Edit as needed or enter manually."
                    )
                    yield Label("Amount ($):")
                    yield Input(placeholder="0.00", id="pp_amount", type="number")
                    yield Label("Description:")
                    yield Input(
                        placeholder="What is this transaction for?", id="pp_description"
                    )

                # Step 3: Customer Details
                with Vertical(classes="form-subsection"):
                    yield Label("Step 3: Customer Details", classes="subtitle")
                    yield Label("Customer Name:")
                    yield Input(
                        placeholder="First and Last Name", id="pp_customer_name"
                    )
                    yield Label(
                        "Customer Email (required to send a receipt for cash transactions):"
                    )
                    yield Input(
                        placeholder="customer@example.com", id="pp_customer_email"
                    )
                    yield Label("Customer Phone (optional):")
                    yield Input(placeholder="Phone number", id="pp_customer_phone")

                with Horizontal(classes="filter-row"):
                    yield Button(
                        pos_btn_label, variant="success", id="btn_pp_process"
                    )
                    yield Button(
                        "Record Cash Transaction",
                        variant="warning",
                        id="btn_pp_cash",
                    )
                    yield Button("Clear", id="btn_pp_clear")

                yield Label("Recent Transactions:", classes="subtitle")
                # Customer columns are intentionally omitted — this table is
                # visible on a shared login screen where other visitors may see it.
                yield DataTable(id="pp_txns_table")
                yield Button("Refresh", id="btn_pp_refresh")

            with Horizontal(classes="filter-row"):
                yield Button("Close", variant="error", id="btn_pp_close")

    def on_mount(self):
        # Available items table
        avail = self.query_one("#pp_inv_available_table", DataTable)
        avail.add_column("ID", width=5)
        avail.add_column("Name", width=28)
        avail.add_column("Description", width=35)
        avail.add_column("Price", width=10)
        avail.cursor_type = "row"
        self._load_inv_available()

        # Cart table
        cart = self.query_one("#pp_inv_cart_table", DataTable)
        cart.add_column("Item", width=28)
        cart.add_column("Qty", width=6)
        cart.add_column("Unit Price", width=12)
        cart.add_column("Subtotal", width=12)
        cart.cursor_type = "row"

        # Transaction history table
        table = self.query_one("#pp_txns_table", DataTable)
        table.add_columns("ID", "Date", "Amount", "Description", "Status", "Via")
        self._load_transactions()

    def _load_inv_available(self):
        """Populates the available items table from the active inventory."""
        table = self.query_one("#pp_inv_available_table", DataTable)
        table.clear()
        for item in services.get_all_inventory_items():
            table.add_row(
                str(item.id), item.name, item.description or "", f"${item.price:.2f}"
            )

    def _rebuild_cart(self):
        """
        Rebuilds the cart DataTable from _cart state, then auto-fills the
        amount and description fields with the computed total and item names.
        """
        table = self.query_one("#pp_inv_cart_table", DataTable)
        table.clear()
        total = 0.0
        for entry in self._cart:
            subtotal = entry["qty"] * entry["unit_price"]
            total += subtotal
            table.add_row(
                entry["name"],
                str(entry["qty"]),
                f"${entry['unit_price']:.2f}",
                f"${subtotal:.2f}",
                key=str(entry["id"]),
            )
        self.query_one("#pp_inv_cart_total_lbl").update(f"Cart Total: ${total:.2f}")
        try:
            self.query_one("#pp_amount", Input).value = f"{total:.2f}" if total else ""
            if self._cart:
                desc_parts = [
                    f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
                    for e in self._cart
                ]
                self.query_one("#pp_description", Input).value = ", ".join(desc_parts)
            else:
                self.query_one("#pp_description", Input).value = ""
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "pp_inv_available_table":
            row_data = event.data_table.get_row(event.row_key)
            self._inv_selected_item = {
                "id": int(row_data[0]),
                "name": str(row_data[1]),
                "price": float(str(row_data[3]).lstrip("$")),
            }
        elif event.data_table.id == "pp_inv_cart_table":
            self._inv_selected_cart_item_id = int(event.row_key.value)
            self.query_one("#btn_pp_remove_from_cart").disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_pp_add_to_cart":
            self._add_to_cart()
        elif event.button.id == "btn_pp_remove_from_cart":
            self._remove_from_cart()
        elif event.button.id == "btn_pp_clear_cart":
            self._clear_cart()
        elif event.button.id == "btn_pp_process":
            self._process_transaction()
        elif event.button.id == "btn_pp_cash":
            self._record_cash()
        elif event.button.id == "btn_pp_clear":
            self._clear_form()
        elif event.button.id == "btn_pp_refresh":
            self._load_transactions()
        elif event.button.id == "btn_pp_close":
            self.dismiss()

    def _add_to_cart(self):
        if not self._inv_selected_item:
            self.app.notify(
                "Click an item in the table to select it first.", severity="warning"
            )
            return
        try:
            qty = float(self.query_one("#pp_inv_qty", Input).value or "1")
            if qty <= 0:
                self.app.notify("Quantity must be greater than zero.", severity="error")
                return
        except ValueError:
            qty = 1.0

        for entry in self._cart:
            if entry["id"] == self._inv_selected_item["id"]:
                entry["qty"] += qty
                self._rebuild_cart()
                return

        self._cart.append({
            "id": self._inv_selected_item["id"],
            "name": self._inv_selected_item["name"],
            "qty": qty,
            "unit_price": self._inv_selected_item["price"],
        })
        self._rebuild_cart()

    def _remove_from_cart(self):
        if self._inv_selected_cart_item_id is None:
            self.app.notify("Select a cart row first.", severity="warning")
            return
        self._cart = [
            e for e in self._cart if e["id"] != self._inv_selected_cart_item_id
        ]
        self._inv_selected_cart_item_id = None
        self.query_one("#btn_pp_remove_from_cart").disabled = True
        self._rebuild_cart()

    def _clear_cart(self):
        self._cart = []
        self._inv_selected_cart_item_id = None
        try:
            self.query_one("#btn_pp_remove_from_cart").disabled = True
        except Exception:
            pass
        self._rebuild_cart()

    def _load_transactions(self):
        """
        Refreshes any pending Square Terminal checkouts from the API, then
        populates the table with recent transactions, hiding customer details.
        """
        square_service.refresh_pending_transactions()
        table = self.query_one("#pp_txns_table", DataTable)
        table.clear()
        for txn in square_service.get_recent_transactions(limit=20):
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
                txn.square_status.replace("_", " ").title(),
                via,
            )

    def _read_form(self):
        """
        Reads and validates form inputs. Returns a dict on success or None if
        validation fails (notification already shown to the user).
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
        """Resets all form inputs and clears the cart."""
        for field_id in (
            "pp_amount",
            "pp_customer_name",
            "pp_customer_email",
            "pp_customer_phone",
            "pp_description",
        ):
            self.query_one(f"#{field_id}", Input).value = ""
        self._clear_cart()
