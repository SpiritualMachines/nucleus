"""Feedback viewing modal for the dashboard."""

__all__ = [
    "FeedbackViewModal",
]

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown

from core import services


class FeedbackViewModal(ModalScreen):
    """View and Reply to Feedback."""

    def __init__(self, fb_id: int):
        super().__init__()
        self.fb_id = fb_id

    def compose(self) -> ComposeResult:
        fb = services.get_feedback_by_id(self.fb_id)

        with Vertical(classes="splash-container"):
            if not fb:
                yield Label("Feedback not found.", classes="error")
                yield Button("Close", id="btn_close")
                return

            yield Label(f"Feedback #{fb.id}", classes="title")
            yield Label(f"From: {fb.first_name} {fb.last_name}")
            yield Label(f"Date: {fb.submitted_at}")

            yield Label("Comment:", classes="subtitle")
            with VerticalScroll(classes="splash-content"):
                yield Markdown(fb.comment)

            yield Label("Admin Response:", classes="subtitle")
            yield Input(fb.admin_response or "", id="admin_response")

            with Horizontal(classes="filter-row"):
                yield Button("Save Response", variant="success", id="btn_save")
                yield Button("Close", id="btn_close")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_close":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            resp = self.query_one("#admin_response").value
            services.update_feedback_response(self.fb_id, resp)
            self.app.notify("Response Saved")
            self.dismiss(True)
