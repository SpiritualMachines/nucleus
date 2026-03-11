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

PRONOUN_OPTIONS = [
    "She/Her",
    "They/Them",
    "He/Him",
    "She/They",
    "He/They",
    "Prefer not to say",
    "Prefer to self-describe",
]

AGE_RANGE_OPTIONS = [
    "Under 18",
    "18-24",
    "25-34",
    "35-44",
    "45-54",
    "55-64",
    "65 and Over",
]

HOW_HEARD_OPTIONS = [
    "Friend/Colleague",
    "Social Media",
    "Library",
    "Postcard/Poster",
    "Community Organization",
    "Other",
]


class CommunityContactModal(ModalScreen):
    """
    Walk-in contact form accessible from the login screen without requiring a
    member account. Captures basic contact details, visit reason, demographic
    info, and outreach opt-ins.

    Staff can check the Unknown walk-in box to bypass required fields and
    log an anonymous tour visit with a single submission.
    """

    def compose(self) -> ComposeResult:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        with Vertical(classes="splash-container"):
            yield Label("Community Contact", classes="title")
            with VerticalScroll(classes="splash-content"):
                # --- Contact Info ---
                yield Label("First Name (required)")
                yield Input(placeholder="First Name", id="cc_first_name")

                yield Label("Last Name")
                yield Input(placeholder="Last Name (optional)", id="cc_last_name")

                yield Label("Phone")
                yield Input(placeholder="Phone (optional)", id="cc_phone")

                yield Label("Email (required)")
                yield Input(placeholder="Email", id="cc_email")

                yield Label("Postal Code")
                yield Input(placeholder="Postal code (optional)", id="cc_postal_code")

                # --- Pronouns ---
                yield Label("Pronouns (Optional)", classes="subtitle")
                with RadioSet(id="cc_pronouns"):
                    yield RadioButton("-- Skip --", value=True)
                    for option in PRONOUN_OPTIONS:
                        yield RadioButton(option)

                # --- Age Range ---
                yield Label("Age Range (Optional)", classes="subtitle")
                with RadioSet(id="cc_age_range"):
                    yield RadioButton("-- Skip --", value=True)
                    for option in AGE_RANGE_OPTIONS:
                        yield RadioButton(option)

                # --- What Brought You In ---
                yield Label("What Brought You In? (Optional)", classes="subtitle")
                with RadioSet(id="cc_brought_in"):
                    yield RadioButton("-- Skip --", value=True)
                    for option in BROUGHT_IN_OPTIONS:
                        yield RadioButton(option)

                yield Label("Other (please specify)")
                yield Input(placeholder="Describe other reason...", id="cc_other")

                # --- How Did You Hear About Us ---
                yield Label("How Did You Hear About Us? (Optional)", classes="subtitle")
                with RadioSet(id="cc_how_heard"):
                    yield RadioButton("-- Skip --", value=True)
                    for option in HOW_HEARD_OPTIONS:
                        yield RadioButton(option)

                # --- Stay Connected opt-ins ---
                yield Label("Let's Stay Connected!", classes="subtitle")
                yield Checkbox(
                    "Yes, I'd like to receive updates about workshops, events, and opportunities",
                    id="cc_opt_in_updates",
                )
                yield Checkbox(
                    "I might be interested in volunteering",
                    id="cc_opt_in_volunteer",
                )
                yield Checkbox(
                    "I might be interested in teaching/mentoring",
                    id="cc_opt_in_teaching",
                )

                # --- Visit Metadata ---
                yield Label("Date / Time")
                yield Input(now_str, id="cc_datetime")

                yield Checkbox("Tour Given", id="cc_tour_given")
                yield Checkbox("(Staff Only) Unknown", id="cc_tour")

                yield Label(
                    "Staff Name and Description (required for Unknown walk-in record)"
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
        is_unknown = self.query_one("#cc_tour", Checkbox).value
        tour_given = self.query_one("#cc_tour_given", Checkbox).value
        staff_name = self.query_one("#cc_staff_name", Input).value.strip() or None
        visited_at = self._parse_datetime()

        if is_unknown:
            # Unknown walk-in — visitor fields are optional since there may be no
            # individual to record. Staff name is required for accountability.
            if not staff_name:
                self.app.notify(
                    "Staff Name and Description is required for an Unknown walk-in record.",
                    severity="error",
                )
                return
            services.save_community_contact(
                first_name="Unknown",
                email="",
                visited_at=visited_at,
                is_community_tour=tour_given,
                staff_name=staff_name,
            )
            self.app.notify("Walk-in recorded.")
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

        # Resolve radio selections — index 0 is the skip sentinel in each set.
        brought_in_by = self._radio_value("#cc_brought_in", BROUGHT_IN_OPTIONS)
        pronouns = self._radio_value("#cc_pronouns", PRONOUN_OPTIONS)
        age_range = self._radio_value("#cc_age_range", AGE_RANGE_OPTIONS)
        how_heard = self._radio_value("#cc_how_heard", HOW_HEARD_OPTIONS)

        services.save_community_contact(
            first_name=first_name,
            email=email,
            last_name=self.query_one("#cc_last_name", Input).value.strip() or None,
            phone=self.query_one("#cc_phone", Input).value.strip() or None,
            postal_code=self.query_one("#cc_postal_code", Input).value.strip() or None,
            brought_in_by=brought_in_by,
            other_reason=self.query_one("#cc_other", Input).value.strip() or None,
            visited_at=visited_at,
            is_community_tour=tour_given,
            staff_name=staff_name,
            pronouns=pronouns,
            age_range=age_range,
            how_heard=how_heard,
            opt_in_updates=self.query_one("#cc_opt_in_updates", Checkbox).value,
            opt_in_volunteer=self.query_one("#cc_opt_in_volunteer", Checkbox).value,
            opt_in_teaching=self.query_one("#cc_opt_in_teaching", Checkbox).value,
        )
        self.app.notify("Contact recorded. Thank you!")
        self.dismiss(True)

    def _radio_value(self, radio_set_id: str, options: list) -> str | None:
        """
        Returns the selected option string from a RadioSet, or None when the
        first (skip sentinel) option is selected. Index 0 always maps to skip.
        """
        radio_set = self.query_one(radio_set_id, RadioSet)
        pressed = radio_set.pressed_index
        if pressed > 0:
            return options[pressed - 1]
        return None

    def _parse_datetime(self) -> datetime:
        """Parses the datetime input, falling back to now on invalid format."""
        val = self.query_one("#cc_datetime", Input).value.strip()
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M")
        except ValueError:
            return datetime.now()
