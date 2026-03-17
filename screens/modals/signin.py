"""Sign-in and sign-out related modals for the dashboard."""

__all__ = [
    "SelectVisitTypeModal",
    "ConfirmSignOutScreen",
    "PostActionCountdownModal",
]

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList

from screens.modals import VISIT_TYPES


class SelectVisitTypeModal(ModalScreen):
    """
    Prompts the user to choose their visit type before signing in.
    Dismisses with the selected type string, or None if cancelled.
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Welcome! Select Visit Type", classes="title")
            yield Label("What brings you in today?", classes="subtitle")
            yield OptionList(*VISIT_TYPES, id="visit_type_list")
            with Horizontal(classes="filter-row"):
                yield Button("Cancel", variant="error", id="vtype_cancel")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(str(event.option.prompt))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "vtype_cancel":
            self.dismiss(None)


class ConfirmSignOutScreen(ModalScreen):
    """A simple confirmation modal for signing out."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Sign Out?", classes="title")
            yield Label(
                "Are you sure you want to sign out of the space?", classes="title"
            )

            # Buttons
            with Horizontal(classes="filter-row"):
                yield Button("Yes, Sign Out", variant="warning", id="confirm_yes")
                yield Button("Cancel", variant="primary", id="confirm_no")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm_yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class PostActionCountdownModal(ModalScreen):
    """
    Shown immediately after a space sign-in or sign-out.
    Counts down from 10 seconds and triggers an app logout when it reaches
    zero, giving the next person a clean session. The current user can click
    Stay Signed In to cancel the countdown and remain on the dashboard.
    """

    COUNTDOWN_SECONDS = 10

    def __init__(self, message: str):
        super().__init__()
        self.message = message
        self._remaining = self.COUNTDOWN_SECONDS

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label(self.message, classes="title")
            yield Label(
                f"Logging out in {self._remaining} seconds...",
                id="countdown_label",
            )
            with Horizontal(classes="filter-row"):
                yield Button("Stay Signed In", variant="success", id="btn_stay")

    def on_mount(self):
        self.set_interval(1.0, self._tick)

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self.dismiss(False)
        else:
            self.query_one("#countdown_label").update(
                f"Logging out in {self._remaining} seconds..."
            )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_stay":
            self.dismiss(True)
