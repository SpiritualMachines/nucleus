"""Storage unit management modals for the dashboard."""

__all__ = [
    "StorageAssignModal",
    "StorageViewModal",
    "StorageEditModal",
]

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, DataTable, Input, Label, Select

from core import services


class StorageAssignModal(ModalScreen):
    """
    Modal for assigning an occupant and item details to a storage unit.
    Staff select the target unit from a dropdown populated at open time,
    then enter a freeform name or search for a registered member.
    The charges section is hidden until the 'Charges Owed' checkbox is ticked.
    On submit the modal dismisses with True so the caller can reload its table.
    """

    def __init__(self, units: list, **kwargs):
        """
        units -- list of StorageUnit instances to populate the unit selector.
        """
        super().__init__(**kwargs)
        self.units = units
        # Account number resolved when staff selects a row from the member search
        self._resolved_acct: int | None = None

    def compose(self) -> ComposeResult:
        unit_options = [
            (f"{u.unit_number} - {u.description}", u.id) for u in self.units
        ]
        with Vertical(classes="splash-container"):
            yield Label("Assign to Storage Unit", classes="title")
            with VerticalScroll(classes="splash-content"):
                yield Label("Storage Unit:")
                yield Select(unit_options, id="storage_unit_select")

                yield Label("Assigned To (name, or search for a user below):")
                yield Input(placeholder="First and Last Name", id="storage_name")

                yield Label("Search User (optional):")
                with Horizontal(classes="search-row"):
                    yield Input(placeholder="Name or email...", id="storage_search")
                    yield Button("Search", id="btn_storage_search")
                    yield Button("Clear Search", id="btn_storage_clear_search")
                yield DataTable(id="storage_search_table")

                yield Label("Item Description:")
                yield Input(placeholder="What is being stored?", id="storage_item_desc")

                yield Label("Notes (optional):")
                yield Input(placeholder="Any additional notes", id="storage_notes")

                with Collapsible(
                    title="Charges Owed",
                    id="storage_charges_collapsible",
                    collapsed=True,
                ):
                    yield Label("Charge Type:")
                    yield Input(
                        placeholder="e.g. Filament, Large Format Printer",
                        id="storage_charge_type",
                    )
                    yield Label("Number of Units:")
                    yield Input(
                        placeholder="1", id="storage_charge_unit_count", type="number"
                    )
                    yield Label("Cost per Unit ($):")
                    yield Input(
                        placeholder="0.00",
                        id="storage_charge_cost_per_unit",
                        type="number",
                    )
                    yield Label("Total: $0.00", id="storage_charge_total_lbl")
                    yield Label("Charge Notes (optional):")
                    yield Input(
                        placeholder="Additional details about the charges",
                        id="storage_charge_notes",
                    )

                with Horizontal(classes="filter-row"):
                    yield Button("Assign", variant="success", id="btn_storage_assign")
                    yield Button("Cancel", variant="error", id="btn_storage_cancel")

    def on_mount(self):
        # Set up the member search results table
        table = self.query_one("#storage_search_table", DataTable)
        table.add_columns("Acct #", "Name", "Email")
        table.cursor_type = "row"

    def on_input_changed(self, event: Input.Changed):
        """Recalculate and display the charge total whenever a charge amount field changes."""
        if event.input.id in (
            "storage_charge_unit_count",
            "storage_charge_cost_per_unit",
        ):
            self._update_charge_total()

    def _update_charge_total(self):
        try:
            count = float(
                self.query_one("#storage_charge_unit_count", Input).value or "0"
            )
            cost = float(
                self.query_one("#storage_charge_cost_per_unit", Input).value or "0"
            )
            total = round(count * cost, 2)
            self.query_one("#storage_charge_total_lbl").update(f"Total: ${total:.2f}")
        except (ValueError, TypeError):
            self.query_one("#storage_charge_total_lbl").update("Total: $0.00")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_storage_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_storage_search":
            self._search_users()
        elif event.button.id == "btn_storage_clear_search":
            self._clear_search()
        elif event.button.id == "btn_storage_assign":
            self._submit()

    def _search_users(self):
        query = self.query_one("#storage_search", Input).value.strip()
        if not query:
            self.app.notify("Enter a name or email to search.", severity="warning")
            return
        table = self.query_one("#storage_search_table", DataTable)
        table.clear()
        self._resolved_acct = None
        results = services.search_users(query)
        if not results:
            self.app.notify("No users found.", severity="warning")
            return
        for u in results:
            table.add_row(
                str(u.account_number), f"{u.first_name} {u.last_name}", u.email
            )

    def _clear_search(self):
        """Clears the search input, results table, and resolved account."""
        self.query_one("#storage_search", Input).value = ""
        self.query_one("#storage_search_table", DataTable).clear()
        self._resolved_acct = None
        self.query_one("#storage_name", Input).value = ""

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "storage_search_table":
            row_data = event.data_table.get_row(event.row_key)
            self._resolved_acct = int(row_data[0])
            name = str(row_data[1])
            self.query_one("#storage_name", Input).value = name
            self.app.notify(f"Selected: {name}")

    def _submit(self):
        unit_value = self.query_one("#storage_unit_select", Select).value
        if unit_value is Select.BLANK:
            self.app.notify("Select a storage unit.", severity="error")
            return
        unit_id = int(unit_value)

        assigned_to_name = self.query_one("#storage_name", Input).value.strip() or None
        item_description = (
            self.query_one("#storage_item_desc", Input).value.strip() or None
        )
        notes = self.query_one("#storage_notes", Input).value.strip() or None
        collapsible = self.query_one("#storage_charges_collapsible", Collapsible)
        charges_owed = not collapsible.collapsed

        charge_type = None
        charge_unit_count = None
        charge_cost_per_unit = None
        charge_notes = None

        if charges_owed:
            charge_type = (
                self.query_one("#storage_charge_type", Input).value.strip() or None
            )
            try:
                charge_unit_count = float(
                    self.query_one("#storage_charge_unit_count", Input).value or "0"
                )
            except ValueError:
                charge_unit_count = None
            try:
                charge_cost_per_unit = float(
                    self.query_one("#storage_charge_cost_per_unit", Input).value or "0"
                )
            except ValueError:
                charge_cost_per_unit = None
            charge_notes = (
                self.query_one("#storage_charge_notes", Input).value.strip() or None
            )

        services.create_storage_assignment(
            unit_id=unit_id,
            assigned_to_name=assigned_to_name,
            user_account_number=self._resolved_acct,
            item_description=item_description,
            notes=notes,
            charges_owed=charges_owed,
            charge_type=charge_type,
            charge_unit_count=charge_unit_count,
            charge_cost_per_unit=charge_cost_per_unit,
            charge_notes=charge_notes,
        )
        self.app.notify("Storage assignment saved.")
        self.dismiss(True)


class StorageViewModal(ModalScreen):
    """
    Read-only detail view for a storage assignment rendered as a two-column table.
    Shows every field including all charge information. Dismisses with False
    so the caller does not need to reload the table after viewing.
    """

    def __init__(self, assignment_id: int, **kwargs):
        super().__init__(**kwargs)
        self._assignment_id = assignment_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Storage Assignment Details", classes="title")
            with VerticalScroll(classes="splash-content"):
                yield DataTable(id="storage_view_table", show_cursor=False)
            with Horizontal(classes="filter-row"):
                yield Button("Close", variant="primary", id="btn_storage_view_close")

    def on_mount(self):
        table = self.query_one("#storage_view_table", DataTable)
        table.add_columns("Field", "Value")

        assignment = services.get_storage_assignment_by_id(self._assignment_id)
        if not assignment:
            table.add_row("Error", "Assignment not found.")
            return

        unit = services.get_storage_unit_by_id(assignment.unit_id)
        unit_label = (
            f"{unit.unit_number} - {unit.description}"
            if unit
            else str(assignment.unit_id)
        )

        status = (
            f"Archived on {assignment.archived_at.strftime('%Y-%m-%d %H:%M')}"
            if assignment.archived_at
            else "Active"
        )

        rows = [
            ("Storage Unit", unit_label),
            ("Assigned To", assignment.assigned_to_name or "Not specified"),
            (
                "Member Account Number",
                str(assignment.user_account_number)
                if assignment.user_account_number
                else "None",
            ),
            ("Item Description", assignment.item_description or "Not specified"),
            ("Notes", assignment.notes or "None"),
            ("Assigned At", assignment.assigned_at.strftime("%Y-%m-%d %H:%M")),
            ("Status", status),
            ("Charges Owed", "Yes" if assignment.charges_owed else "No"),
        ]

        if assignment.charges_owed:
            rows += [
                ("Charge Type", assignment.charge_type or "Not specified"),
                (
                    "Number of Units",
                    str(assignment.charge_unit_count)
                    if assignment.charge_unit_count is not None
                    else "Not specified",
                ),
                (
                    "Cost per Unit",
                    f"${assignment.charge_cost_per_unit:.2f}"
                    if assignment.charge_cost_per_unit is not None
                    else "Not specified",
                ),
                (
                    "Total Charges",
                    f"${assignment.charge_total:.2f}"
                    if assignment.charge_total is not None
                    else "Not calculated",
                ),
                ("Charge Notes", assignment.charge_notes or "None"),
            ]

        for field, value in rows:
            table.add_row(field, value)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_storage_view_close":
            self.dismiss(False)


class StorageEditModal(ModalScreen):
    """
    Editable form for updating an existing active storage assignment.
    Pre-populated from the existing record. On save, calls update_storage_assignment
    and dismisses with True so the caller can reload the table.
    """

    def __init__(self, assignment, units: list, **kwargs):
        """
        assignment -- the StorageAssignment instance to edit.
        units      -- list of active StorageUnit instances for the unit selector.
        """
        super().__init__(**kwargs)
        self._assignment = assignment
        self.units = units
        # Preserve any already-resolved member account from the existing record
        self._resolved_acct: int | None = assignment.user_account_number

    def compose(self) -> ComposeResult:
        a = self._assignment
        unit_options = [
            (f"{u.unit_number} - {u.description}", u.id) for u in self.units
        ]
        charges_collapsed = not a.charges_owed

        with Vertical(classes="splash-container"):
            yield Label("Edit Storage Assignment", classes="title")
            with VerticalScroll(classes="splash-content"):
                yield Label("Storage Unit:")
                yield Select(
                    unit_options, value=a.unit_id, id="edit_storage_unit_select"
                )

                yield Label("Assigned To (name, or search for a user below):")
                yield Input(
                    a.assigned_to_name or "",
                    placeholder="First and Last Name",
                    id="edit_storage_name",
                )

                yield Label("Search User (optional):")
                with Horizontal(classes="search-row"):
                    yield Input(
                        placeholder="Name or email...", id="edit_storage_search"
                    )
                    yield Button("Search", id="btn_edit_storage_search")
                    yield Button("Clear Search", id="btn_edit_storage_clear_search")
                yield DataTable(id="edit_storage_search_table")

                yield Label("Item Description:")
                yield Input(
                    a.item_description or "",
                    placeholder="What is being stored?",
                    id="edit_storage_item_desc",
                )

                yield Label("Notes (optional):")
                yield Input(
                    a.notes or "",
                    placeholder="Any additional notes",
                    id="edit_storage_notes",
                )

                with Collapsible(
                    title="Charges Owed",
                    id="edit_storage_charges_collapsible",
                    collapsed=charges_collapsed,
                ):
                    yield Label("Charge Type:")
                    yield Input(
                        a.charge_type or "",
                        placeholder="e.g. Filament, Large Format Printer",
                        id="edit_storage_charge_type",
                    )
                    yield Label("Number of Units:")
                    yield Input(
                        str(a.charge_unit_count)
                        if a.charge_unit_count is not None
                        else "",
                        placeholder="1",
                        id="edit_storage_charge_unit_count",
                        type="number",
                    )
                    yield Label("Cost per Unit ($):")
                    yield Input(
                        str(a.charge_cost_per_unit)
                        if a.charge_cost_per_unit is not None
                        else "",
                        placeholder="0.00",
                        id="edit_storage_charge_cost_per_unit",
                        type="number",
                    )
                    existing_total = (
                        f"Total: ${a.charge_total:.2f}"
                        if a.charge_total is not None
                        else "Total: $0.00"
                    )
                    yield Label(existing_total, id="edit_storage_charge_total_lbl")
                    yield Label("Charge Notes (optional):")
                    yield Input(
                        a.charge_notes or "",
                        placeholder="Additional details about the charges",
                        id="edit_storage_charge_notes",
                    )

                with Horizontal(classes="filter-row"):
                    yield Button(
                        "Save Changes", variant="success", id="btn_edit_storage_save"
                    )
                    yield Button(
                        "Cancel", variant="error", id="btn_edit_storage_cancel"
                    )

    def on_mount(self):
        table = self.query_one("#edit_storage_search_table", DataTable)
        table.add_columns("Acct #", "Name", "Email")
        table.cursor_type = "row"

    def on_input_changed(self, event: Input.Changed):
        """Recalculate and display the charge total whenever a charge amount field changes."""
        if event.input.id in (
            "edit_storage_charge_unit_count",
            "edit_storage_charge_cost_per_unit",
        ):
            self._update_charge_total()

    def _update_charge_total(self):
        try:
            count = float(
                self.query_one("#edit_storage_charge_unit_count", Input).value or "0"
            )
            cost = float(
                self.query_one("#edit_storage_charge_cost_per_unit", Input).value or "0"
            )
            total = round(count * cost, 2)
            self.query_one("#edit_storage_charge_total_lbl").update(
                f"Total: ${total:.2f}"
            )
        except (ValueError, TypeError):
            self.query_one("#edit_storage_charge_total_lbl").update("Total: $0.00")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_edit_storage_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_edit_storage_search":
            self._search_users()
        elif event.button.id == "btn_edit_storage_clear_search":
            self._clear_search()
        elif event.button.id == "btn_edit_storage_save":
            self._submit()

    def _search_users(self):
        query = self.query_one("#edit_storage_search", Input).value.strip()
        if not query:
            self.app.notify("Enter a name or email to search.", severity="warning")
            return
        table = self.query_one("#edit_storage_search_table", DataTable)
        table.clear()
        self._resolved_acct = None
        results = services.search_users(query)
        if not results:
            self.app.notify("No users found.", severity="warning")
            return
        for u in results:
            table.add_row(
                str(u.account_number), f"{u.first_name} {u.last_name}", u.email
            )

    def _clear_search(self):
        """Clears the search input, results table, and resolved account."""
        self.query_one("#edit_storage_search", Input).value = ""
        self.query_one("#edit_storage_search_table", DataTable).clear()
        self._resolved_acct = None
        self.query_one("#edit_storage_name", Input).value = ""

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "edit_storage_search_table":
            row_data = event.data_table.get_row(event.row_key)
            self._resolved_acct = int(row_data[0])
            name = str(row_data[1])
            self.query_one("#edit_storage_name", Input).value = name
            self.app.notify(f"Selected: {name}")

    def _submit(self):
        unit_value = self.query_one("#edit_storage_unit_select", Select).value
        if unit_value is Select.BLANK:
            self.app.notify("Select a storage unit.", severity="error")
            return
        unit_id = int(unit_value)

        assigned_to_name = (
            self.query_one("#edit_storage_name", Input).value.strip() or None
        )
        item_description = (
            self.query_one("#edit_storage_item_desc", Input).value.strip() or None
        )
        notes = self.query_one("#edit_storage_notes", Input).value.strip() or None
        collapsible = self.query_one("#edit_storage_charges_collapsible", Collapsible)
        charges_owed = not collapsible.collapsed

        charge_type = None
        charge_unit_count = None
        charge_cost_per_unit = None
        charge_notes = None

        if charges_owed:
            charge_type = (
                self.query_one("#edit_storage_charge_type", Input).value.strip() or None
            )
            try:
                charge_unit_count = float(
                    self.query_one("#edit_storage_charge_unit_count", Input).value
                    or "0"
                )
            except ValueError:
                charge_unit_count = None
            try:
                charge_cost_per_unit = float(
                    self.query_one("#edit_storage_charge_cost_per_unit", Input).value
                    or "0"
                )
            except ValueError:
                charge_cost_per_unit = None
            charge_notes = (
                self.query_one("#edit_storage_charge_notes", Input).value.strip()
                or None
            )

        result = services.update_storage_assignment(
            assignment_id=self._assignment.id,
            unit_id=unit_id,
            assigned_to_name=assigned_to_name,
            user_account_number=self._resolved_acct,
            item_description=item_description,
            notes=notes,
            charges_owed=charges_owed,
            charge_type=charge_type,
            charge_unit_count=charge_unit_count,
            charge_cost_per_unit=charge_cost_per_unit,
            charge_notes=charge_notes,
        )
        if result:
            self.app.notify("Storage assignment updated.")
            self.dismiss(True)
        else:
            self.app.notify("Could not save: assignment not found.", severity="error")
