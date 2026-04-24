"""Storage tab mixin for Dashboard.

Owns all member storage assignment behaviour: loading, assigning, viewing,
editing, and archiving storage units.
Methods here expect ``self`` to be a live Dashboard instance so that
``self.query_one``, ``self.app``, etc. resolve correctly.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Label

from core import services
from screens.dashboard_modals import (
    StorageAssignModal,
    StorageEditModal,
    StorageViewModal,
)


class StorageMixin:
    """Mixin providing storage tab compose and CRUD methods."""

    def _compose_storage_tab(self) -> ComposeResult:
        """Yields widgets for the Storage tab."""
        with VerticalScroll(id="storage-tab-scroll"):
            yield Label("Member Storage", classes="title")

            # Active storage assignments
            yield Label("Active Storage Assignments", classes="subtitle")
            yield DataTable(id="storage_active_table")
            with Horizontal(classes="filter-row"):
                yield Button(
                    "Assign Storage",
                    variant="success",
                    id="btn_storage_assign",
                )
                yield Button(
                    "View Selected",
                    id="btn_storage_view",
                    disabled=True,
                )
                yield Button(
                    "Edit Selected",
                    variant="primary",
                    id="btn_storage_edit",
                    disabled=True,
                )
                yield Button(
                    "Remove Selected (Archive)",
                    variant="error",
                    id="btn_storage_archive",
                    disabled=True,
                )
                yield Button("Refresh", id="btn_storage_refresh")

            # Archived storage assignments
            yield Label("Archived Storage Assignments", classes="subtitle")
            yield DataTable(id="storage_archived_table")

    def load_storage_assignments(self):
        """Loads active and archived assignment rows into the Storage tab tables."""
        try:
            active_table = self.query_one("#storage_active_table", DataTable)
            archived_table = self.query_one("#storage_archived_table", DataTable)
        except Exception:
            return

        active_table.clear()
        for a in services.get_active_storage_assignments():
            unit = services.get_storage_unit_by_id(a.unit_id)
            unit_label = unit.unit_number if unit else str(a.unit_id)
            name = a.assigned_to_name or ""
            total = f"${a.charge_total:.2f}" if a.charge_total is not None else ""
            active_table.add_row(
                str(a.id),
                unit_label,
                name,
                a.item_description or "",
                a.notes or "",
                a.charge_type or "",
                total,
                a.assigned_at.strftime("%Y-%m-%d %H:%M"),
            )

        archived_table.clear()
        for a in services.get_archived_storage_assignments():
            unit = services.get_storage_unit_by_id(a.unit_id)
            unit_label = unit.unit_number if unit else str(a.unit_id)
            name = a.assigned_to_name or ""
            total = f"${a.charge_total:.2f}" if a.charge_total is not None else ""
            archived_at = (
                a.archived_at.strftime("%Y-%m-%d %H:%M") if a.archived_at else ""
            )
            archived_table.add_row(
                str(a.id),
                unit_label,
                name,
                a.item_description or "",
                a.charge_type or "",
                total,
                archived_at,
            )

    def open_storage_assign_modal(self):
        """
        Opens the StorageAssignModal. The modal includes a unit selector dropdown
        so staff can choose which unit to assign without a separate picker step.
        """
        units = services.get_all_storage_units()
        if not units:
            self.app.notify(
                "No storage units exist. Create units in Settings > Storage Units first.",
                severity="warning",
            )
            return
        self.app.push_screen(
            StorageAssignModal(units=units),
            self._after_storage_assign,
        )

    def _after_storage_assign(self, result: bool):
        """Reloads the storage tables after a successful assignment."""
        if result:
            self.load_storage_assignments()

    def open_storage_view_modal(self):
        """Opens the read-only view modal for the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        self.app.push_screen(
            StorageViewModal(assignment_id=self.selected_storage_assignment_id)
        )

    def open_storage_edit_modal(self):
        """Opens the edit modal for the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        assignment = services.get_storage_assignment_by_id(
            self.selected_storage_assignment_id
        )
        if not assignment:
            self.app.notify("Assignment not found.", severity="error")
            return
        units = services.get_all_storage_units()
        self.app.push_screen(
            StorageEditModal(assignment=assignment, units=units),
            self._after_storage_edit,
        )

    def _after_storage_edit(self, result: bool):
        """Reloads the storage tables after a successful edit."""
        if result:
            self.load_storage_assignments()

    def archive_storage_assignment(self):
        """Archives the currently selected active assignment."""
        if not self.selected_storage_assignment_id:
            self.app.notify("Select an assignment row first.", severity="warning")
            return
        ok = services.archive_storage_assignment(self.selected_storage_assignment_id)
        if ok:
            self.app.notify("Storage assignment archived.")
            self.selected_storage_assignment_id = None
            self.query_one("#btn_storage_view").disabled = True
            self.query_one("#btn_storage_edit").disabled = True
            self.query_one("#btn_storage_archive").disabled = True
        else:
            self.app.notify(
                "Could not archive: already archived or not found.", severity="error"
            )
        self.load_storage_assignments()
