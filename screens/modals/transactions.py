"""Transaction and credit balance modals for the dashboard."""

__all__ = [
    "TransactionModal",
    "ViewCreditsModal",
    "RefundConfirmModal",
    "EditTransactionModal",
    "EditAllocationModal",
]

from datetime import datetime, timedelta

from sqlmodel import Session
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, DataTable, Input, Label, Select

from core import models, services, square_service
from core.database import engine


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

            with Collapsible(title="Transaction Details", collapsed=False):
                yield Label("Amount ($):")
                yield Input(placeholder="0.00", type="number", id="txn_amount")
                yield Label("Description:")
                yield Input(placeholder="e.g., 3D Print Filament", id="txn_desc")

            with Collapsible(title="Payment Method", collapsed=False):
                with Horizontal(classes="filter-row"):
                    if self.initial_type == "credit":
                        # For credit: show payment buttons
                        square_label = (
                            "Process Square Transaction"
                            if self.square_enabled
                            else "Process Transaction (Local)"
                        )
                        yield Button(
                            square_label, variant="success", id="btn_pay_square"
                        )
                        yield Button(
                            "Record as Cash", variant="warning", id="btn_pay_cash"
                        )
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


class RefundConfirmModal(ModalScreen):
    """
    Confirmation dialog for issuing a refund against a SquareTransaction.
    Requires staff to enter a reason before the refund can be submitted.
    Dismisses with the reason string on confirm, or None on cancel.
    """

    def __init__(self, txn_id: int, amount: float, customer_name: str):
        super().__init__()
        self.txn_id = txn_id
        self.amount = amount
        self.customer_name = customer_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Issue Refund", classes="title")
            yield Label(
                f"Transaction #{self.txn_id} - {self.customer_name} - ${self.amount:.2f}",
                classes="subtitle",
            )
            yield Label("Refund Reason (required):")
            yield Input(placeholder="Enter reason for refund", id="refund_reason")
            with Horizontal(classes="filter-row"):
                yield Button("Confirm Refund", variant="error", id="btn_confirm_refund")
                yield Button("Cancel", id="btn_cancel_refund")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_refund":
            self.dismiss(None)
        elif event.button.id == "btn_confirm_refund":
            reason = self.query_one("#refund_reason", Input).value.strip()
            if not reason:
                self.app.notify("A refund reason is required.", severity="error")
                return
            self.dismiss(reason)


class EditTransactionModal(ModalScreen):
    """Allows staff to correct customer info and description on a SquareTransaction."""

    def __init__(self, txn_id: int):
        super().__init__()
        self.txn_id = txn_id
        self._txn = square_service.get_transaction_by_id(txn_id)

    def compose(self) -> ComposeResult:
        t = self._txn
        with Vertical(classes="splash-container scrollable"):
            yield Label(f"Edit Transaction #{self.txn_id}", classes="title")

            yield Label("Customer Name:")
            yield Input(t.customer_name or "", id="edit_customer_name")

            yield Label("Customer Email:")
            yield Input(t.customer_email or "", id="edit_customer_email")

            yield Label("Customer Phone:")
            yield Input(t.customer_phone or "", id="edit_customer_phone")

            yield Label("Description:")
            yield Input(t.description or "", id="edit_description")

            yield Label("Processed By:")
            yield Input(t.processed_by or "", id="edit_processed_by")

            with Horizontal(classes="filter-row"):
                yield Button("Save", variant="success", id="btn_save")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            self._save()

    def _save(self):
        try:
            with Session(engine) as session:
                txn = session.get(models.SquareTransaction, self.txn_id)
                if not txn:
                    self.app.notify("Transaction not found.", severity="error")
                    return
                txn.customer_name = self.query_one(
                    "#edit_customer_name", Input
                ).value.strip()
                txn.customer_email = (
                    self.query_one("#edit_customer_email", Input).value.strip() or None
                )
                txn.customer_phone = (
                    self.query_one("#edit_customer_phone", Input).value.strip() or None
                )
                txn.description = (
                    self.query_one("#edit_description", Input).value.strip() or None
                )
                txn.processed_by = (
                    self.query_one("#edit_processed_by", Input).value.strip() or None
                )
                txn.updated_at = datetime.now()
                session.add(txn)
                session.commit()
            self.app.notify(f"Transaction #{self.txn_id} updated.")
            self.dismiss(True)
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")


class EditAllocationModal(ModalScreen):
    """Lets staff split a bulk SquareTransaction into multiple typed line items.

    Staff add line items one at a time (Day Pass, Membership, Product, or Custom),
    each with its own amount, until the transaction total is accounted for.
    On save, the appropriate activation records are created (DayPass,
    ActiveMembership) and the transaction description is updated to reflect
    the full breakdown.

    Example: a $17.00 manual transaction is reallocated as a $15.00 Day Pass
    for a specific member plus a $2.00 product sale, creating the DayPass record
    and updating the description to "Day Pass: John Smith, 2x Snack".
    """

    _ITEM_TYPES = [
        ("Custom", "custom"),
        ("Day Pass", "daypass"),
        ("Membership", "membership"),
        ("Product", "product"),
    ]

    def __init__(self, txn_id: int):
        super().__init__()
        self.txn_id = txn_id
        self._txn = square_service.get_transaction_by_id(txn_id)
        self._item_type = "custom"
        # Selected user for daypass/membership form (reset when switching type)
        self._form_user_acct: int | None = None
        self._form_user_name: str = ""
        # List of committed line items — each is a dict with all data needed on save
        self._items: list = []
        self._selected_item_row: int | None = None
        # Full inventory item list loaded at mount so we can look up IDs by row index
        self._inventory_items: list = []

    def compose(self) -> ComposeResult:
        t = self._txn
        with VerticalScroll(classes="splash-container"):
            yield Label(
                f"Edit Allocation - Transaction #{self.txn_id}", classes="title"
            )
            yield Label(
                f"Total: ${t.amount:.2f}  |  Current: {t.description or '(no description)'}",
                classes="subtitle",
            )
            # Live running totals updated as items are added/removed
            yield Label(
                "Allocated: $0.00  |  Remaining: $0.00",
                id="lbl_totals",
                classes="subtitle",
            )

            yield Label("Add Item", classes="subtitle")
            yield Label("Item Type:")
            yield Select(self._ITEM_TYPES, id="item_type_select", value="custom")

            # --- Custom: free-text description ---
            with Vertical(id="section_custom"):
                yield Label("Description:")
                yield Input(
                    t.description or "",
                    id="custom_desc",
                    placeholder="e.g. Workshop fee",
                )

            # --- Day Pass ---
            with Vertical(id="section_daypass", classes="hidden"):
                yield Label(
                    "Search for a registered user (optional — leave blank for guest):"
                )
                with Horizontal(classes="search-row"):
                    yield Input(placeholder="Name or email...", id="dp_user_search")
                    yield Button("Search", id="btn_dp_search")
                yield DataTable(id="dp_user_table")
                yield Label("Date (YYYY-MM-DD):")
                yield Input(t.created_at.strftime("%Y-%m-%d"), id="dp_date")
                yield Label("Description:")
                yield Input("Day Pass", id="dp_desc")

            # --- Membership ---
            with Vertical(id="section_membership", classes="hidden"):
                yield Label("Search for a registered user (required):")
                with Horizontal(classes="search-row"):
                    yield Input(placeholder="Name or email...", id="mem_user_search")
                    yield Button("Search", id="btn_mem_search")
                yield DataTable(id="mem_user_table")
                yield Label("Start Date (YYYY-MM-DD):")
                yield Input(t.created_at.strftime("%Y-%m-%d"), id="mem_start")
                yield Label("End Date (YYYY-MM-DD):")
                yield Input(
                    (t.created_at + timedelta(days=30)).strftime("%Y-%m-%d"),
                    id="mem_end",
                )
                yield Label("Description:")
                yield Input("Membership", id="mem_desc")

            # --- Product ---
            with Vertical(id="section_product", classes="hidden"):
                yield Label("Select a product:")
                yield DataTable(id="products_table")
                with Horizontal(classes="filter-row"):
                    yield Label("Qty:")
                    yield Input("1", id="prod_qty", type="number")

            # Amount is always visible; auto-fills for products on row selection
            yield Label("Amount ($):")
            yield Input(placeholder="0.00", id="item_amount", type="number")

            yield Button("Add Line Item", variant="primary", id="btn_add_line_item")

            yield Label("Allocation", classes="subtitle")
            yield DataTable(id="alloc_table")
            with Horizontal(classes="filter-row"):
                yield Button(
                    "Remove Selected",
                    variant="error",
                    id="btn_remove_item",
                    disabled=True,
                )

            with Horizontal(classes="filter-row"):
                yield Button("Save Allocation", variant="success", id="btn_save_alloc")
                yield Button("Cancel", id="btn_cancel_alloc")

    def on_mount(self):
        self._inventory_items = services.get_all_inventory_items()
        prod_table = self.query_one("#products_table", DataTable)
        prod_table.cursor_type = "row"
        prod_table.add_columns("Name", "Unit Price")
        for item in self._inventory_items:
            prod_table.add_row(item.name, f"${item.price:.2f}")

        alloc_table = self.query_one("#alloc_table", DataTable)
        alloc_table.cursor_type = "row"
        alloc_table.add_columns("Type", "Description", "Amount", "User")

        for table_id in ("dp_user_table", "mem_user_table"):
            t = self.query_one(f"#{table_id}", DataTable)
            t.cursor_type = "row"
            t.add_columns("Acct #", "Name", "Email")

        self._refresh_totals()

    def on_select_changed(self, event: Select.Changed):
        if event.select.id != "item_type_select":
            return
        self._item_type = str(event.value)
        self._form_user_acct = None
        self._form_user_name = ""
        for key, selector in (
            ("custom", "#section_custom"),
            ("daypass", "#section_daypass"),
            ("membership", "#section_membership"),
            ("product", "#section_product"),
        ):
            widget = self.query_one(selector)
            if key == self._item_type:
                widget.remove_class("hidden")
            else:
                widget.add_class("hidden")
        # Clear amount when switching types so stale values don't carry over
        self.query_one("#item_amount", Input).value = ""

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        table_id = event.data_table.id
        row = event.data_table.get_row(event.row_key)

        if table_id == "dp_user_table":
            self._form_user_acct = int(row[0])
            self._form_user_name = str(row[1])
            self.app.notify(f"User selected: {row[1]}")

        elif table_id == "mem_user_table":
            self._form_user_acct = int(row[0])
            self._form_user_name = str(row[1])
            self.app.notify(f"User selected: {row[1]}")

        elif table_id == "products_table":
            # Auto-fill amount from unit price times qty
            try:
                unit_price = float(str(row[1]).lstrip("$"))
                qty_str = self.query_one("#prod_qty", Input).value
                qty = max(1, int(qty_str)) if qty_str else 1
                self.query_one("#item_amount", Input).value = f"{unit_price * qty:.2f}"
            except (ValueError, IndexError):
                pass

        elif table_id == "alloc_table":
            self._selected_item_row = event.data_table.cursor_row
            self.query_one("#btn_remove_item").disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        btn = event.button.id
        if btn == "btn_cancel_alloc":
            self.dismiss(False)
        elif btn == "btn_dp_search":
            self._search_users("dp_user_search", "dp_user_table")
        elif btn == "btn_mem_search":
            self._search_users("mem_user_search", "mem_user_table")
        elif btn == "btn_add_line_item":
            self._add_line_item()
        elif btn == "btn_remove_item":
            self._remove_line_item()
        elif btn == "btn_save_alloc":
            self._save()

    def _search_users(self, input_id: str, table_id: str):
        query = self.query_one(f"#{input_id}", Input).value.strip()
        if not query:
            return
        results = services.search_users(query)
        table = self.query_one(f"#{table_id}", DataTable)
        table.clear()
        for u in results:
            table.add_row(
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                u.email,
            )

    def _add_line_item(self):
        """Validates the current form state and commits one line item to the allocation list."""
        try:
            amount = float(self.query_one("#item_amount", Input).value or "0")
        except ValueError:
            self.app.notify("Enter a valid amount.", severity="warning")
            return

        if self._item_type == "custom":
            desc = self.query_one("#custom_desc", Input).value.strip()
            if not desc:
                self.app.notify("Enter a description.", severity="warning")
                return
            item = {
                "type": "custom",
                "description": desc,
                "amount": amount,
                "user_acct": None,
                "user_name": "",
            }

        elif self._item_type == "daypass":
            date_str = self.query_one("#dp_date", Input).value.strip()
            desc = self.query_one("#dp_desc", Input).value.strip() or "Day Pass"
            try:
                date_dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                self.app.notify("Invalid date format (YYYY-MM-DD).", severity="error")
                return
            item = {
                "type": "daypass",
                "description": desc,
                "amount": amount,
                "user_acct": self._form_user_acct,
                "user_name": self._form_user_name,
                "date": date_dt,
            }

        elif self._item_type == "membership":
            if not self._form_user_acct:
                self.app.notify(
                    "Search for and select a user first.", severity="warning"
                )
                return
            try:
                start_dt = datetime.strptime(
                    self.query_one("#mem_start", Input).value.strip(), "%Y-%m-%d"
                )
                end_dt = datetime.strptime(
                    self.query_one("#mem_end", Input).value.strip(), "%Y-%m-%d"
                )
            except ValueError:
                self.app.notify("Invalid date format (YYYY-MM-DD).", severity="error")
                return
            desc = self.query_one("#mem_desc", Input).value.strip() or "Membership"
            item = {
                "type": "membership",
                "description": desc,
                "amount": amount,
                "user_acct": self._form_user_acct,
                "user_name": self._form_user_name,
                "start_date": start_dt,
                "end_date": end_dt,
            }

        elif self._item_type == "product":
            prod_table = self.query_one("#products_table", DataTable)
            if prod_table.cursor_row is None:
                self.app.notify("Select a product row first.", severity="warning")
                return
            cursor = prod_table.cursor_row
            try:
                row = prod_table.get_row_at(cursor)
            except Exception:
                self.app.notify("Select a product row first.", severity="warning")
                return
            try:
                qty = max(1, int(self.query_one("#prod_qty", Input).value or "1"))
            except ValueError:
                qty = 1
            name = str(row[0])
            unit_price = float(str(row[1]).lstrip("$"))
            inv_item = (
                self._inventory_items[cursor]
                if cursor < len(self._inventory_items)
                else None
            )
            desc = f"{qty}x {name}"
            item = {
                "type": "product",
                "description": desc,
                "amount": amount,
                "user_acct": None,
                "user_name": "",
                "inventory_item_id": inv_item.id if inv_item else None,
                "item_name": name,
                "unit_price": unit_price,
                "quantity": qty,
            }

        else:
            return

        self._items.append(item)
        alloc_table = self.query_one("#alloc_table", DataTable)
        alloc_table.add_row(
            item["type"].title(),
            item["description"],
            f"${item['amount']:.2f}",
            item.get("user_name", ""),
        )
        self._refresh_totals()
        # Reset amount after adding
        self.query_one("#item_amount", Input).value = ""

    def _remove_line_item(self):
        if self._selected_item_row is None or not self._items:
            return
        idx = self._selected_item_row
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
        alloc_table = self.query_one("#alloc_table", DataTable)
        alloc_table.clear()
        for entry in self._items:
            alloc_table.add_row(
                entry["type"].title(),
                entry["description"],
                f"${entry['amount']:.2f}",
                entry.get("user_name", ""),
            )
        self._selected_item_row = None
        self.query_one("#btn_remove_item").disabled = True
        self._refresh_totals()

    def _refresh_totals(self):
        """Updates the allocated / remaining label based on current line items."""
        allocated = sum(e["amount"] for e in self._items)
        remaining = self._txn.amount - allocated
        self.query_one("#lbl_totals", Label).update(
            f"Allocated: ${allocated:.2f}  |  Remaining: ${remaining:.2f}"
        )

    def _save(self):
        """Creates activation records for each line item and updates the transaction description."""
        if not self._items:
            self.app.notify("Add at least one line item.", severity="warning")
            return

        try:
            with Session(engine) as session:
                for item in self._items:
                    if item["type"] == "daypass" and item.get("user_acct"):
                        session.add(
                            models.DayPass(
                                user_account_number=item["user_acct"],
                                date=item["date"],
                                description=item["description"],
                            )
                        )
                    elif item["type"] == "membership" and item.get("user_acct"):
                        session.add(
                            models.ActiveMembership(
                                user_account_number=item["user_acct"],
                                start_date=item["start_date"],
                                end_date=item["end_date"],
                                description=item["description"],
                            )
                        )
                    elif item["type"] == "product" and item.get("inventory_item_id"):
                        session.add(
                            models.ProductSale(
                                transaction_id=self.txn_id,
                                inventory_item_id=item["inventory_item_id"],
                                item_name=item["item_name"],
                                unit_price=item["unit_price"],
                                quantity=item["quantity"],
                            )
                        )

                combined_desc = ", ".join(
                    (
                        f"{e['description']} ({e['user_name']})"
                        if e.get("user_name")
                        else e["description"]
                    )
                    for e in self._items
                )
                txn = session.get(models.SquareTransaction, self.txn_id)
                if txn:
                    txn.description = combined_desc
                    txn.updated_at = datetime.now()
                    session.add(txn)

                session.commit()

            self.app.notify(
                f"Transaction #{self.txn_id} split into {len(self._items)} item(s)."
            )
            self.dismiss(True)

        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
