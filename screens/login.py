from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from core import services
from core.config import settings
from screens.community_contact import CommunityContactModal
from screens.dashboard import Dashboard
from screens.public_purchase import PublicPurchaseModal
from screens.registration import RegisterScreen


class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        logo = services.get_setting("ascii_logo", settings.ASCII_LOGO)
        hackspace_name = services.get_setting("hackspace_name", settings.HACKSPACE_NAME)
        app_name = services.get_setting("app_name", settings.APP_NAME)
        app_version = settings.APP_VERSION
        with Container(classes="login-container"):
            yield Static(logo, classes="logo-art")
            yield Label(hackspace_name, classes="login-hackspace-name")
            yield Label(f"{app_name} {app_version}", classes="login-app-name")

            yield Label("Please Login")
            yield Input(placeholder="Email", id="email")
            yield Input(placeholder="Password", password=True, id="password")
            yield Button("Login", variant="primary", id="login_btn")
            yield Button(
                "Register New Account",
                variant="primary",
                id="register_btn",
            )
            yield Button(
                "Community Contacts",
                variant="default",
                id="community_btn",
            )
            yield Button(
                "Manual Purchase",
                variant="default",
                id="manual_purchase_btn",
            )
            yield Label("", id="error_msg", classes="error")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "login_btn":
            self.attempt_login()
        elif event.button.id == "register_btn":
            self.app.push_screen(RegisterScreen())
        elif event.button.id == "community_btn":
            self.app.push_screen(CommunityContactModal())
        elif event.button.id == "manual_purchase_btn":
            self.app.push_screen(PublicPurchaseModal())

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "email":
            self.query_one("#password").focus()
        elif event.input.id == "password":
            self.attempt_login()

    def attempt_login(self):
        email = self.query_one("#email").value
        pwd = self.query_one("#password").value
        try:
            user = services.authenticate_user(email, pwd)
        except ValueError as e:
            # authenticate_user raises ValueError when an account is locked
            self.query_one("#error_msg").update(str(e))
            return

        if user:
            if user.banned:
                self.query_one("#error_msg").update("Account Banned.")
            else:
                self.app.current_user = user

                # Clear credentials immediately after successful authentication
                self.query_one("#email").value = ""
                self.query_one("#password").value = ""
                self.query_one("#error_msg").update("")

                self.app.push_screen(Dashboard())
        else:
            self.query_one("#error_msg").update("Invalid Credentials")
