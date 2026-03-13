from email_validator import EmailNotValidError, validate_email
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from core import services


class ChangePasswordScreen(ModalScreen):
    """A modal dialog to change password."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container scrollable"):
            yield Label("Change Password", classes="title")
            yield Input(placeholder="Current Password", password=True, id="old_pass")
            yield Input(placeholder="New Password", password=True, id="new_pass")
            yield Input(placeholder="Confirm New", password=True, id="confirm_pass")

            yield Button("Save Password", variant="success", id="save_pwd")
            yield Button("Cancel", variant="error", id="cancel_pwd")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel_pwd":
            self.dismiss()
        elif event.button.id == "save_pwd":
            self.action_save()

    def action_save(self):
        old = self.query_one("#old_pass").value
        new = self.query_one("#new_pass").value
        confirm = self.query_one("#confirm_pass").value

        if not old or not new:
            self.app.notify("Please fill in all fields", severity="error")
            return

        if new != confirm:
            self.app.notify("New passwords do not match", severity="error")
            return

        try:
            services.update_user_password(
                self.app.current_user.account_number, old, new
            )
            self.app.notify("Password Updated Successfully!")
            self.dismiss()
        except Exception as e:
            self.app.notify(str(e), severity="error")


class EditProfileScreen(ModalScreen):
    """A modal dialog to edit user details."""

    def compose(self) -> ComposeResult:
        u = self.app.current_user

        # UPDATED: Uses splash-container for the larger 80% width look
        with Vertical(classes="splash-container scrollable"):
            yield Label("Edit My Information", classes="title")

            # Contact
            yield Label("Contact Info")
            yield Input(u.email, placeholder="Email Address", id="edit_email")
            yield Input(u.phone, placeholder="Phone", id="edit_phone")

            # Address
            yield Label("Address")
            yield Input(u.street_address, placeholder="Street Address", id="edit_addr")
            yield Input(u.city, placeholder="City", id="edit_city")
            yield Input(u.province, placeholder="Province", id="edit_prov")
            yield Input(u.postal_code, placeholder="Postal Code", id="edit_postal")

            # Emergency
            yield Label("Emergency Contact")
            yield Input(
                u.emergency_first_name,
                placeholder="Contact First Name",
                id="edit_em_fname",
            )
            yield Input(
                u.emergency_last_name,
                placeholder="Contact Last Name",
                id="edit_em_lname",
            )
            yield Input(
                u.emergency_phone, placeholder="Contact Phone", id="edit_em_phone"
            )

            # Health
            yield Label("Health & Safety")
            yield Input(u.allergies or "", placeholder="Allergies", id="edit_allergies")
            yield Input(
                u.health_concerns or "",
                placeholder="Health Concerns",
                id="edit_health",
            )

            yield Button("Save Changes", variant="success", id="save_edit")
            yield Button("Cancel", variant="error", id="cancel_edit")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel_edit":
            self.dismiss()
        elif event.button.id == "save_edit":
            self.submit_changes()

    def submit_changes(self):
        try:
            # 1. Email Validation
            raw_email = self.query_one("#edit_email").value
            try:
                valid = validate_email(raw_email)
                normalized_email = valid.email
            except EmailNotValidError as e:
                self.app.notify(f"Invalid Email: {str(e)}", severity="error")
                return

            # 2. Phone Validation & Formatting
            raw_phone = self.query_one("#edit_phone").value
            phone_digits = "".join(filter(str.isdigit, raw_phone))
            if len(phone_digits) != 10:
                self.app.notify("Phone number must be 10 digits.", severity="error")
                return
            formatted_phone = (
                f"{phone_digits[:3]}-{phone_digits[3:6]}-{phone_digits[6:]}"
            )

            # 3. Gather data
            data = {
                "email": normalized_email,
                "phone": formatted_phone,
                "street_address": self.query_one("#edit_addr").value,
                "city": self.query_one("#edit_city").value,
                "province": self.query_one("#edit_prov").value,
                "postal_code": self.query_one("#edit_postal").value,
                "emergency_first_name": self.query_one("#edit_em_fname").value,
                "emergency_last_name": self.query_one("#edit_em_lname").value,
                "emergency_phone": self.query_one("#edit_em_phone").value,
                "allergies": self.query_one("#edit_allergies").value,
                "health_concerns": self.query_one("#edit_health").value,
            }

            # Update DB
            updated_user = services.update_user_details(
                self.app.current_user.account_number, data
            )
            # Update local session user
            self.app.current_user = updated_user
            self.app.notify("Profile Updated!")
            # Return True to trigger dashboard refresh
            self.dismiss(result=True)

        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")
