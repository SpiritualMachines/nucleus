"""POS / purchases / transactions mixin for Dashboard.

Owns all Point-of-Sale, inventory cart, and transaction-history behaviour.
Methods here expect ``self`` to be a live Dashboard instance so that
``self.query_one``, ``self.app``, etc. resolve correctly.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, DataTable, Input, Label

from core import models, services, square_service
from core.email_service import send_transaction_receipt
from screens.modals import (
    EditAllocationModal,
    EditTransactionModal,
    RefundConfirmModal,
)


class POSMixin:
    """Mixin providing POS, purchases tab, and transaction management methods."""

    def _compose_purchases_tab(self, user, currency) -> ComposeResult:
        """Yields widgets for the Purchases tab."""
        with VerticalScroll():
            yield Label("Purchases", classes="title")

            # === STAFF / ADMIN VIEW ===
            if user.role in [models.UserRole.STAFF, models.UserRole.ADMIN]:
                # Subsection 0: Manual Transaction (Point of Sale)
                with Vertical(classes="purchase-section"):
                    pos_cfg = square_service.get_pos_config()
                    pos_btn_label = (
                        "Send to Square Terminal"
                        if pos_cfg.square_enabled
                        else "Record Transaction"
                    )
                    yield Label("Manual Transaction", classes="subtitle")

                    # Step 1: Inventory Cart
                    with Collapsible(
                        title="Step 1: Select Items (Optional)", collapsed=True
                    ):
                        yield Label(
                            "Click an item row to select it, set the quantity,"
                            " then click Add to Cart."
                            " Amount and Description are auto-filled."
                        )
                        yield DataTable(id="inv_available_table")
                        with Horizontal(classes="filter-row"):
                            yield Label("Quantity:")
                            yield Input("1", id="inv_qty", type="number")
                            yield Button(
                                "Add to Cart",
                                variant="primary",
                                id="btn_add_to_cart",
                            )

                    # Step 2: Add a custom line item not in the inventory list
                    with Collapsible(
                        title="Step 2: Add Custom Item (Optional)", collapsed=True
                    ):
                        yield Label(
                            "Add charges not covered by the inventory above,"
                            " e.g. a workshop fee or donation."
                        )
                        yield Label("Item Name / Description:")
                        yield Input(
                            placeholder="e.g. Workshop fee, Donation",
                            id="pos_manual_desc",
                        )
                        yield Label("Price ($):")
                        yield Input(
                            placeholder="0.00",
                            id="pos_manual_price",
                            type="number",
                        )
                        with Horizontal(classes="filter-row"):
                            yield Button(
                                "Add Custom Item",
                                variant="primary",
                                id="btn_add_manual_to_cart",
                            )

                    # Step 3: Customer Details
                    with Collapsible(title="Step 3: Customer Details", collapsed=True):
                        yield Label(
                            "Search for an existing user to auto-fill, or"
                            " enter details manually:"
                        )
                        with Horizontal(classes="search-row"):
                            yield Input(
                                placeholder="Search by name or email...",
                                id="pos_customer_search_input",
                            )
                            yield Button(
                                "Search",
                                id="btn_pos_customer_search",
                            )
                        yield DataTable(id="pos_customer_search_table")

                        yield Label("Customer Name:")
                        yield Input(
                            placeholder="First and Last Name",
                            id="pos_customer_name",
                        )
                        yield Label(
                            "Customer Email (required to send a receipt for cash transactions):"
                        )
                        yield Input(
                            placeholder="customer@example.com",
                            id="pos_customer_email",
                        )
                        yield Label("Customer Phone (optional):")
                        yield Input(
                            placeholder="Phone number",
                            id="pos_customer_phone",
                        )

                    yield Label("Cart:", classes="subtitle")
                    yield DataTable(id="inv_cart_table")
                    with Horizontal(classes="filter-row"):
                        yield Label("Cart Total: $0.00", id="inv_cart_total_lbl")
                        yield Button(
                            "Remove Selected",
                            variant="error",
                            id="btn_remove_from_cart",
                            disabled=True,
                        )
                        yield Button("Clear Cart", id="btn_clear_cart")

                    with Horizontal(classes="filter-row"):
                        yield Button(
                            pos_btn_label,
                            variant="success",
                            id="btn_process_manual_txn",
                        )
                        yield Button(
                            "Record Cash Transaction",
                            variant="warning",
                            id="btn_record_cash_txn",
                        )
                        yield Button(
                            "Clear Form",
                            id="btn_clear_pos_form",
                        )

                # Subsection 1: Existing User Transactions (consolidated)
                with Collapsible(
                    title="Membership Transactions",
                    collapsed=True,
                    classes="purchase-section",
                ):
                    yield Label(
                        "Search for a user to manage their memberships, day passes, and credits:"
                    )
                    with Horizontal(classes="search-row"):
                        yield Input(
                            placeholder="Name or Email...",
                            id="user_search_input",
                        )
                        yield Button("Search", id="btn_user_search")
                    yield DataTable(id="user_search_table")
                    yield Label("Actions for Selected User:", classes="subtitle")
                    yield Label(
                        "Search for a user above to enable actions.",
                        classes="text-muted",
                        id="lbl_no_user_hint",
                    )
                    # Row 1: Membership actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Membership",
                            variant="success",
                            id="btn_add_mem",
                            disabled=True,
                        )
                        yield Button(
                            "Edit Memberships",
                            variant="primary",
                            id="btn_edit_mem",
                            disabled=True,
                        )
                    # Row 2: Day Pass actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Add Day Pass",
                            variant="success",
                            id="btn_add_daypass",
                            disabled=True,
                        )
                        yield Button(
                            "View Day Passes",
                            variant="primary",
                            id="btn_view_daypass",
                            disabled=True,
                        )
                    # Row 3: Credits actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            f"Add {currency} (+)",
                            variant="success",
                            id="btn_credit",
                            disabled=True,
                        )
                        yield Button(
                            f"Deduct {currency} (-)",
                            variant="error",
                            id="btn_debit",
                            disabled=True,
                        )
                        yield Button(
                            f"View {currency}",
                            variant="primary",
                            id="btn_view_credits",
                            disabled=True,
                        )
                    # Row 4: Square subscription actions
                    with Horizontal(classes="filter-row"):
                        yield Button(
                            "Activate Square Membership Subscription",
                            variant="success",
                            id="btn_activate_subscription",
                            disabled=True,
                        )
                        yield Button(
                            "Cancel Subscription",
                            variant="error",
                            id="btn_cancel_subscription",
                            disabled=True,
                        )
                        yield Button(
                            "Poll Subscription Status",
                            variant="primary",
                            id="btn_poll_subscription",
                            disabled=True,
                        )

            # === REGULAR USER VIEW ===
            else:
                # Subsection 1: My Memberships
                with Collapsible(
                    title="My Memberships", collapsed=False, classes="purchase-section"
                ):
                    yield DataTable(id="my_mem_table")

                # Subsection 2: My Day Passes
                with Collapsible(
                    title="My Day Passes", collapsed=False, classes="purchase-section"
                ):
                    yield DataTable(id="my_daypass_table")

                # Subsection 3: My Consumables
                with Collapsible(
                    title=f"My {currency} Ledger",
                    collapsed=False,
                    classes="purchase-section",
                ):
                    yield Label(f"{currency} Balance: $0.00", id="my_balance_lbl")
                    yield DataTable(id="my_cons_table")

    def _compose_transactions_tab(self) -> ComposeResult:
        """Yields widgets for the Transactions tab.

        Displays a flat, always-visible table covering all SquareTransaction
        records plus free daypass and free membership activations that would
        not otherwise appear in the POS history.
        """
        with VerticalScroll():
            yield Label("Transactions", classes="title")
            yield DataTable(id="all_txns_table")
            with Horizontal(classes="filter-row"):
                yield Button("Refresh", id="btn_refresh_all_txns")
                yield Button(
                    "Check Terminal Status",
                    variant="primary",
                    id="btn_check_txn_status",
                    disabled=True,
                )
                yield Button(
                    "Issue Refund",
                    variant="error",
                    id="btn_issue_refund_txn",
                    disabled=True,
                )
            with Horizontal(classes="filter-row"):
                yield Button(
                    "Edit Details",
                    variant="primary",
                    id="btn_edit_txn_details",
                    disabled=True,
                )
                yield Button(
                    "Edit Allocation",
                    variant="warning",
                    id="btn_edit_txn_allocation",
                    disabled=True,
                )

    def _load_all_transactions(self):
        """Refreshes pending Square checkouts then reloads the Transactions tab table.

        Refreshing before loading ensures auto-cancelled Square Terminal checkouts
        are shown with their final status rather than stuck on Pending.
        """
        square_service.refresh_pending_transactions()
        try:
            table = self.query_one("#all_txns_table", DataTable)
        except Exception:
            return
        table.clear()
        self.selected_pos_txn_id = None
        for btn_id in (
            "#btn_check_txn_status",
            "#btn_issue_refund_txn",
            "#btn_edit_txn_details",
            "#btn_edit_txn_allocation",
        ):
            try:
                self.query_one(btn_id).disabled = True
            except Exception:
                pass

        rows = square_service.get_all_transactions(limit=200)
        for r in rows:
            table.add_row(
                r["id"],
                r["date"].strftime("%Y-%m-%d %H:%M"),
                r["customer_name"][:20],
                r["amount"],
                r["type"],
                (r["description"])[:26],
                r["status"],
                r["via"],
                r["processed_by"][:16],
            )

    def process_manual_transaction(self):
        """
        Reads the manual transaction form, validates inputs, and either sends a
        checkout request to the Square Terminal or records a local transaction
        depending on whether Square is enabled in POS settings.
        """
        if not self._cart:
            self.app.notify(
                "Cart is empty. Add items before processing.", severity="error"
            )
            return

        try:
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        amount = sum(e["qty"] * e["unit_price"] for e in self._cart)
        desc_parts = [
            f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
            for e in self._cart
        ]
        description = ", ".join(desc_parts)

        staff = self.app.current_user
        staff_name = f"{staff.first_name} {staff.last_name}" if staff else None
        ok, message, txn = square_service.process_terminal_checkout(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
            processed_by=staff_name,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            services.record_product_sales(txn.id, self._cart)
            # Only send a receipt when a real payment was submitted to Square.
            # is_local=True means Square was disabled and nothing was actually
            # charged -- the record is an audit placeholder, not a payment confirmation.
            if ok and not txn.is_local and txn.customer_email:
                try:
                    hackspace_name = services.get_setting("hackspace_name", "Nucleus")
                    sent = send_transaction_receipt(
                        txn_id=txn.id,
                        amount=txn.amount,
                        customer_name=txn.customer_name,
                        customer_email=txn.customer_email,
                        description=txn.description or "",
                        payment_method="Card (Square Terminal)",
                        transaction_ref=txn.square_checkout_id or "",
                        transaction_date=txn.created_at.strftime("%Y-%m-%d %H:%M"),
                        subject_override=f"{hackspace_name} - Payment Submitted #{txn.id}",
                    )
                    if sent:
                        self.app.notify(f"Receipt emailed to {txn.customer_email}.")
                except Exception as exc:
                    self.app.notify(f"Receipt email failed: {exc}", severity="warning")
            self.clear_pos_form()
            self._load_all_transactions()

    def record_cash_transaction(self):
        """
        Reads the manual transaction form and records a cash payment either to
        Square (if enabled and configured) or locally. When recorded in Square,
        the transaction appears in Square Dashboard so the bookkeeper only needs
        to reconcile one system.
        """
        if not self._cart:
            self.app.notify(
                "Cart is empty. Add items before recording.", severity="error"
            )
            return

        try:
            customer_name = self.query_one("#pos_customer_name", Input).value.strip()
            customer_email = self.query_one("#pos_customer_email", Input).value.strip()
            customer_phone = self.query_one("#pos_customer_phone", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not customer_name:
            self.app.notify("Customer name is required.", severity="error")
            return

        amount = sum(e["qty"] * e["unit_price"] for e in self._cart)
        desc_parts = [
            f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
            for e in self._cart
        ]
        description = ", ".join(desc_parts)

        staff = self.app.current_user
        staff_name = f"{staff.first_name} {staff.last_name}" if staff else None
        ok, message, txn = square_service.record_cash_payment(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email or None,
            customer_phone=customer_phone or None,
            description=description or None,
            processed_by=staff_name,
        )

        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)

        if txn:
            services.record_product_sales(txn.id, self._cart)
            if ok and txn.customer_email:
                try:
                    sent = send_transaction_receipt(
                        txn_id=txn.id,
                        amount=txn.amount,
                        customer_name=txn.customer_name,
                        customer_email=txn.customer_email,
                        description=txn.description or "",
                        payment_method="Cash",
                        transaction_ref=txn.square_checkout_id or "",
                        transaction_date=txn.created_at.strftime("%Y-%m-%d %H:%M"),
                    )
                    if sent:
                        self.app.notify(f"Receipt emailed to {txn.customer_email}.")
                except Exception as exc:
                    self.app.notify(f"Receipt email failed: {exc}", severity="warning")
            self.clear_pos_form()
            self._load_all_transactions()

    def clear_pos_form(self):
        """Resets all manual transaction input fields and the inventory cart."""
        for field_id in (
            "pos_amount",
            "pos_customer_name",
            "pos_customer_email",
            "pos_customer_phone",
            "pos_description",
            "pos_customer_search_input",
        ):
            try:
                self.query_one(f"#{field_id}", Input).value = ""
            except Exception:
                pass
        try:
            self.query_one("#pos_customer_search_table", DataTable).clear()
        except Exception:
            pass
        self.clear_cart()

    def check_pos_terminal_status(self):
        """
        Queries Square for the current status of the selected transaction and
        updates the local record. Only applicable to Square-processed transactions.
        """
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return
        ok, message = square_service.update_transaction_status(self.selected_pos_txn_id)
        severity = "information" if ok else "error"
        self.app.notify(message, severity=severity)
        if ok:
            self._load_all_transactions()

    def _handle_issue_refund(self):
        """
        Opens the refund confirmation modal for the selected transaction.
        On confirmation, processes the refund and refreshes the table.
        """
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return
        txn = square_service.get_transaction_by_id(self.selected_pos_txn_id)
        if not txn:
            self.app.notify("Transaction not found.", severity="error")
            return

        def on_refund_confirmed(reason: str | None) -> None:
            if not reason:
                return
            staff = self.app.current_user
            staff_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown"
            ok, message = square_service.process_refund(
                txn_id=self.selected_pos_txn_id,
                reason=reason,
                refunded_by=staff_name,
            )
            self.app.notify(message, severity="information" if ok else "error")
            if ok:
                self._load_all_transactions()

        self.app.push_screen(
            RefundConfirmModal(txn.id, txn.amount, txn.customer_name or ""),
            on_refund_confirmed,
        )

    def _handle_edit_txn_details(self):
        """Opens the Edit Transaction modal to correct customer info or description."""
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return

        def on_done(saved: bool):
            if saved:
                self._load_all_transactions()

        self.app.push_screen(EditTransactionModal(self.selected_pos_txn_id), on_done)

    def _handle_edit_txn_allocation(self):
        """Opens the Edit Allocation modal to reclassify what a transaction was for."""
        if not self.selected_pos_txn_id:
            self.app.notify("Select a transaction row first.", severity="warning")
            return

        def on_done(saved: bool):
            if saved:
                self._load_all_transactions()

        self.app.push_screen(EditAllocationModal(self.selected_pos_txn_id), on_done)

    def _load_inv_available_table(self):
        """Populates the available inventory items table in the Purchases tab."""
        try:
            table = self.query_one("#inv_available_table", DataTable)
        except Exception:
            return
        table.clear()
        for item in services.get_all_inventory_items():
            table.add_row(
                str(item.id), item.name, item.description or "", f"${item.price:.2f}"
            )

    def _rebuild_cart_table(self):
        """
        Clears and rebuilds the cart DataTable from _cart, then auto-fills
        pos_amount with the running total and pos_description with item names.
        """
        try:
            table = self.query_one("#inv_cart_table", DataTable)
            total_lbl = self.query_one("#inv_cart_total_lbl")
        except Exception:
            return

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

        total_lbl.update(f"Cart Total: ${total:.2f}")

        # Auto-fill the amount and description fields from cart contents
        try:
            self.query_one("#pos_amount", Input).value = f"{total:.2f}" if total else ""
            if self._cart:
                desc_parts = [
                    f"{e['name']} x{int(e['qty']) if e['qty'] == int(e['qty']) else e['qty']}"
                    for e in self._cart
                ]
                self.query_one("#pos_description", Input).value = ", ".join(desc_parts)
            else:
                self.query_one("#pos_description", Input).value = ""
        except Exception:
            pass

    def add_to_cart(self):
        """Adds the selected available item to the cart, merging qty if already present."""
        if not self._inv_selected_item:
            self.app.notify(
                "Click an item in the table to select it first.", severity="warning"
            )
            return
        try:
            qty = float(self.query_one("#inv_qty", Input).value or "1")
            if qty <= 0:
                self.app.notify("Quantity must be greater than zero.", severity="error")
                return
        except ValueError:
            qty = 1.0

        # Merge with existing cart entry for the same item
        for entry in self._cart:
            if entry["id"] == self._inv_selected_item["id"]:
                entry["qty"] += qty
                self._rebuild_cart_table()
                return

        self._cart.append(
            {
                "id": self._inv_selected_item["id"],
                "name": self._inv_selected_item["name"],
                "qty": qty,
                "unit_price": self._inv_selected_item["price"],
            }
        )
        self._rebuild_cart_table()

    def add_manual_to_cart(self):
        """Adds a custom (manual) line item to the cart from the POS form fields."""
        try:
            desc = self.query_one("#pos_manual_desc", Input).value.strip()
            price_str = self.query_one("#pos_manual_price", Input).value.strip()
        except Exception as e:
            self.app.notify(f"Form error: {e}", severity="error")
            return

        if not desc:
            self.app.notify("Please enter an item name/description.", severity="error")
            return
        try:
            price = float(price_str)
            if price <= 0:
                self.app.notify("Price must be greater than zero.", severity="error")
                return
        except (ValueError, TypeError):
            self.app.notify("Please enter a valid price.", severity="error")
            return

        self._manual_entry_counter += 1
        self._cart.append(
            {
                "id": f"manual_{self._manual_entry_counter}",
                "name": desc,
                "qty": 1,
                "unit_price": price,
            }
        )
        self._rebuild_cart_table()

        # Clear the manual entry fields after adding
        self.query_one("#pos_manual_desc", Input).value = ""
        self.query_one("#pos_manual_price", Input).value = ""

    def remove_from_cart(self):
        """Removes the selected cart row by item ID."""
        if self._inv_selected_cart_item_id is None:
            self.app.notify("Select a cart row first.", severity="warning")
            return
        self._cart = [
            e for e in self._cart if e["id"] != self._inv_selected_cart_item_id
        ]
        self._inv_selected_cart_item_id = None
        try:
            self.query_one("#btn_remove_from_cart").disabled = True
        except Exception:
            pass
        self._rebuild_cart_table()

    def clear_cart(self):
        """Empties the cart and resets all cart-related state."""
        self._cart = []
        self._inv_selected_cart_item_id = None
        try:
            self.query_one("#btn_remove_from_cart").disabled = True
        except Exception:
            pass
        self._rebuild_cart_table()

    def action_pos_customer_search(self):
        """Search for existing users to auto-fill POS customer details."""
        query = self.query_one("#pos_customer_search_input").value.strip()
        table = self.query_one("#pos_customer_search_table", DataTable)
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
                str(u.account_number),
                f"{u.first_name} {u.last_name}",
                u.email,
                u.phone or "",
            )
