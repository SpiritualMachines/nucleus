"""Square subscription activation modal for the dashboard."""

__all__ = [
    "ActivateSubscriptionModal",
]

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from core import services, square_service


class ActivateSubscriptionModal(ModalScreen):
    """
    Confirms and initiates a Square recurring subscription for a member.

    Square handles billing entirely: it emails the member a payment link for
    each billing cycle. Nucleus stores the subscription ID returned by Square
    and polls the status daily to determine whether access should remain active.
    No card data is passed to or stored in Nucleus.
    """

    def __init__(self, acct_num: int):
        super().__init__()
        self.acct_num = acct_num

    def compose(self) -> ComposeResult:
        user = services.get_user_by_account(self.acct_num)
        plan_variation_id = services.get_setting(
            "square_subscription_plan_variation_id", ""
        )
        timezone = services.get_setting(
            "square_subscription_timezone", "America/Toronto"
        )

        with Vertical(classes="splash-container"):
            yield Label("Activate Square Subscription", classes="title")

            if user:
                name = f"{user.first_name} {user.last_name}"
                yield Label(f"Member: {name}", classes="subtitle")
                yield Label(f"Account: #{self.acct_num}", classes="subtitle")
                yield Label(f"Email: {user.email}", classes="subtitle")

                if user.square_subscription_id:
                    yield Label(
                        f"Note: this member already has a subscription on file "
                        f"(ID: {user.square_subscription_id}, "
                        f"Status: {user.square_subscription_status or 'unknown'}). "
                        "Activating will create a new subscription.",
                        classes="text-muted",
                    )

            yield Label("")

            if not plan_variation_id:
                yield Label(
                    "No Plan Variation ID is configured. "
                    "Go to Settings > Subscriptions to set one before activating.",
                    classes="text-error",
                )
                with Horizontal(classes="filter-row"):
                    yield Button("Close", variant="error", id="btn_cancel")
            else:
                yield Label("Square Plan Variation ID:")
                yield Label(plan_variation_id, classes="text-muted")
                yield Label(f"Billing Timezone: {timezone}", classes="text-muted")
                yield Label("")
                yield Label(
                    "Square will email the member a payment link. "
                    "No payment details are stored in Nucleus.",
                    classes="text-muted",
                )
                with Horizontal(classes="filter-row"):
                    yield Button(
                        "Activate Square Membership Subscription",
                        variant="success",
                        id="btn_confirm",
                    )
                    yield Button("Cancel", variant="error", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_confirm":
            plan_variation_id = services.get_setting(
                "square_subscription_plan_variation_id", ""
            )
            timezone = services.get_setting(
                "square_subscription_timezone", "America/Toronto"
            )
            ok, msg = square_service.activate_square_subscription(
                self.acct_num, plan_variation_id, timezone
            )
            if ok:
                self.app.notify(msg, severity="information")
                self.dismiss(True)
            else:
                self.app.notify(msg, severity="error")
