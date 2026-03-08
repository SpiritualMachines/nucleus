from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label


class DirectorySelectScreen(ModalScreen[str]):
    """Modal to select a directory for export."""

    def compose(self) -> ComposeResult:
        # Start at the OS Home Directory
        start_path = str(Path.home())

        with Vertical(classes="splash-container"):
            yield Label("Select Export Directory", classes="title")

            # Display currently selected path
            yield Label("Selected Path:")
            yield Input(start_path, id="selected_path")

            # Tree to navigate
            yield Label("Navigate:", classes="subtitle")
            yield DirectoryTree(start_path, id="dir_tree")

            # Action Buttons
            with Horizontal(classes="filter-row"):
                yield Button("Select", variant="success", id="btn_select")
                yield Button("Cancel", variant="error", id="btn_cancel")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ):
        """When a user clicks a directory in the tree, update the input."""
        self.query_one("#selected_path").value = str(event.path)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_select":
            # Return the path in the input box, trimmed
            path = self.query_one("#selected_path").value.strip()
            self.dismiss(path)
        elif event.button.id == "btn_cancel":
            self.dismiss(None)
