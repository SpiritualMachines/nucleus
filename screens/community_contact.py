from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, RadioButton, RadioSet

from core import services

# Index 0 is the "skip" sentinel — maps to None when saving.
BROUGHT_IN_OPTIONS = [
    "Curiosity",
    "3D Printing",
    "Art",
    "Photography",
    "Film Making",
    "Music/Audio",
    "Referral",
    "Ad/Promotion",
    "Other",
]


class CommunityContactModal(ModalScreen):
    """
    Walk-in contact form accessible from the login screen without requiring a
    member account. Captures basic contact details and visit reason.

    Staff can check the Community Tour Record box to bypass required fields and
    log an anonymous tour visit with a single submission.
    """

    def compose(self) -> ComposeResult:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        with Vertical(classes="splash-container"):
            yield Label("Community Contact", classes="title")
            with VerticalScroll(classes="splash-content"):
                yield Label("First Name (required)")
                yield Input(placeholder="First Name", id="cc_first_name")

                yield Label("Last Name")
                yield Input(placeholder="Last Name (optional)", id="cc_last_name")

                yield Label("Phone")
                yield Input(placeholder="Phone (optional)", id="cc_phone")

                yield Label("Email (required)")
                yield Input(placeholder="Email", id="cc_email")

                yield Label("What Brought You In? (Optional)", classes="subtitle")
                with RadioSet(id="cc_brought_in"):
                    yield RadioButton("-- Skip --", value=True)
                    for option in BROUGHT_IN_OPTIONS:
                        yield RadioButton(option)

                yield Label("Other (please specify)")
                yield Input(placeholder="Describe other reason...", id="cc_other")

                yield Label("Date / Time")
                yield Input(now_str, id="cc_datetime")

                yield Checkbox("(Staff Only) Unknown Walk-In Tour", id="cc_tour")

                yield Label(
                    "Staff Name and Description (required for Unknown Walk-In Tour)"
                )
                yield Input(
                    placeholder="Staff name and notes about the walk-in tour visit",
                    id="cc_staff_name",
                )

            with Horizontal(classes="filter-row"):
                yield Button("Submit", variant="success", id="cc_submit")
                yield Button("Cancel", variant="error", id="cc_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cc_cancel":
            self.dismiss(False)
        elif event.button.id == "cc_submit":
            self._submit()

    def _submit(self):
        is_tour = self.query_one("#cc_tour", Checkbox).value
        staff_name = self.query_one("#cc_staff_name", Input).value.strip() or None
        visited_at = self._parse_datetime()

        if is_tour:
            # Staff community tour — only staff_name is required; all visitor
            # fields are optional since there may be no individual to record.
            if not staff_name:
                self.app.notify(
                    "Staff Name and Description is required for an Unknown Walk-In Tour record.",
                    severity="error",
                )
                return
            services.save_community_contact(
                first_name="Community Tour",
                email="",
                visited_at=visited_at,
                is_community_tour=True,
                staff_name=staff_name,
            )
            self.app.notify("Community tour recorded.")
            self.dismiss(True)
            return

        # Standard submission — validate required fields.
        first_name = self.query_one("#cc_first_name", Input).value.strip()
        email = self.query_one("#cc_email", Input).value.strip()

        if not first_name:
            self.app.notify("First Name is required.", severity="error")
            return
        if not email:
            self.app.notify("Email is required.", severity="error")
            return

        # Resolve radio selection — index 0 is the skip sentinel.
        radio_set = self.query_one("#cc_brought_in", RadioSet)
        pressed = radio_set.pressed_index
        brought_in_by = None
        if pressed > 0:
            brought_in_by = BROUGHT_IN_OPTIONS[pressed - 1]

        other_reason = self.query_one("#cc_other", Input).value.strip() or None

        services.save_community_contact(
            first_name=first_name,
            email=email,
            last_name=self.query_one("#cc_last_name", Input).value.strip() or None,
            phone=self.query_one("#cc_phone", Input).value.strip() or None,
            brought_in_by=brought_in_by,
            other_reason=other_reason,
            visited_at=visited_at,
            is_community_tour=False,
            staff_name=staff_name,
        )
        self.app.notify("Contact recorded. Thank you!")
        self.dismiss(True)

    def _parse_datetime(self) -> datetime:
        """Parses the datetime input, falling back to now on invalid format."""
        val = self.query_one("#cc_datetime", Input).value.strip()
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M")
        except ValueError:
            return datetime.now()
