from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label

from core import services
from core.config import settings
from screens.policies import PolicyScreen


class StaffConfirmScreen(ModalScreen):
    """Popup for staff to confirm ID and Policy checks."""

    def __init__(self, user_data: dict, password: str):
        super().__init__()
        self.user_data = user_data
        self.password = password

    def compose(self) -> ComposeResult:
        with Vertical(classes="splash-container"):
            yield Label("Staff Verification", classes="title")
            yield Label(
                "Please confirm the following before creating this account:",
                classes="title",
            )

            yield Checkbox("I have verified the member's Government ID.", id="chk_id")
            yield Checkbox("I have explained the Code of Conduct.", id="chk_coc")
            yield Checkbox("I have explained the Terms of Service.", id="chk_tos")

            yield Button("Create User Account", variant="success", id="btn_confirm")
            yield Button("Cancel", variant="error", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_confirm":
            chk_id = self.query_one("#chk_id").value
            chk_coc = self.query_one("#chk_coc").value
            chk_tos = self.query_one("#chk_tos").value

            if not (chk_id and chk_coc and chk_tos):
                self.app.notify("All checks are required.", severity="error")
                return

            # Proceed to create user via verified workflow
            try:
                # Update flags in user_data just in case
                self.user_data["id_checked"] = True
                self.user_data["policies_agreed"] = True
                self.user_data["code_of_conduct_agreed"] = True

                services.register_verified_user(self.user_data, self.password)
                self.app.notify("Verified User Created Successfully!")
                self.dismiss(True)  # Return True to parent to close register screen
            except Exception as e:
                self.app.notify(f"Error: {str(e)}", severity="error")


class RegisterScreen(Screen):
    def __init__(self, staff_mode=False):
        super().__init__()
        self.staff_mode = staff_mode

    def compose(self) -> ComposeResult:
        title = (
            "Staff: Register New Member (In-Person)"
            if self.staff_mode
            else "New Member Registration"
        )
        yield Header()
        with Vertical(classes="form-container scrollable"):
            yield Label(title, classes="title")

            yield Label("Account Login", classes="subtitle")
            yield Input(placeholder="Email Address", id="reg_email")
            yield Input(placeholder="Password", password=True, id="reg_pass1")
            yield Input(placeholder="Confirm Password", password=True, id="reg_pass2")

            yield Label("Personal Information", classes="subtitle")
            yield Input(placeholder="First Name", id="reg_fname")
            yield Input(placeholder="Last Name", id="reg_lname")
            yield Input(
                placeholder="Date of Birth (YYYY-MM-DD or YYYY/MM/DD)", id="reg_dob"
            )
            yield Input(placeholder="Phone (10 Digits)", id="reg_phone")

            yield Label("Address", classes="subtitle")
            yield Input(placeholder="Street Address", id="reg_addr")
            yield Input(placeholder="City", id="reg_city")
            yield Input(placeholder="Province", id="reg_prov")
            yield Input(placeholder="Postal Code", id="reg_postal")

            yield Label("Emergency Contact", classes="subtitle")
            yield Input(placeholder="Contact First Name", id="reg_em_fname")
            yield Input(placeholder="Contact Last Name", id="reg_em_lname")
            yield Input(placeholder="Contact Phone", id="reg_em_phone")

            yield Label("Health & Safety", classes="subtitle")
            yield Input(placeholder="Allergies (or 'None')", id="reg_allergies")
            yield Input(placeholder="Health Concerns (Optional)", id="reg_health")

            yield Label(
                f"{services.get_setting('tag_name', settings.TAG_NAME)} Info (Optional)",
                classes="subtitle",
            )
            yield Input(placeholder="Interests / Skills", id="reg_interests")
            yield Input(placeholder="Skills / Tool Training", id="reg_skills")
            yield Input(placeholder="Comments", id="reg_comments")

            yield Label("Agreements", classes="subtitle")
            # If staff mode, these checks are handled in the confirmation popup
            if not self.staff_mode:
                yield Button("Read Terms of Service", id="btn_tos")
                yield Checkbox("I agree to the Terms of Service", id="reg_policies")
                yield Button("Read Code of Conduct", id="btn_coc")
                yield Checkbox("I agree to the Code of Conduct", id="reg_code")

            yield Button("Submit Registration", variant="success", id="btn_submit")
            yield Button("Cancel", variant="error", id="btn_cancel")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.app.pop_screen()
        elif event.button.id == "btn_tos":
            self.app.push_screen(PolicyScreen("Terms of Service", "TOS.txt"))
        elif event.button.id == "btn_coc":
            self.app.push_screen(PolicyScreen("Code of Conduct", "COC.txt"))
        elif event.button.id == "btn_submit":
            self.submit_registration()

    def submit_registration(self):
        # 1. Basic Validation
        email = self.query_one("#reg_email").value.strip()
        p1 = self.query_one("#reg_pass1").value
        p2 = self.query_one("#reg_pass2").value
        fname = self.query_one("#reg_fname").value.strip()
        lname = self.query_one("#reg_lname").value.strip()
        dob_str = self.query_one("#reg_dob").value.strip()
        phone_str = self.query_one("#reg_phone").value.strip()

        if not (email and p1 and p2 and fname and lname and dob_str and phone_str):
            self.app.notify("Please fill in all required fields.", severity="error")
            return

        if p1 != p2:
            self.app.notify("Passwords do not match.", severity="error")
            return

        # 2. Email Validation
        try:
            valid = validate_email(email)
            normalized_email = valid.email
        except EmailNotValidError as e:
            self.app.notify(str(e), severity="error")
            return

        # 3. Date Normalization (User Request: Accept "/" and convert to "-")
        dob_str = dob_str.replace("/", "-")
        try:
            dob_date = datetime.strptime(dob_str, "%Y-%m-%d")
        except ValueError:
            self.app.notify(
                "Invalid Date Format. Use YYYY-MM-DD or YYYY/MM/DD", severity="error"
            )
            return

        # 4. Gather Data
        try:
            # Phone formatting (simple strip)
            phone_digits = "".join(filter(str.isdigit, phone_str))
            if len(phone_digits) != 10:
                self.app.notify("Phone number must be 10 digits.", severity="error")
                return
            formatted_phone = (
                f"{phone_digits[:3]}-{phone_digits[3:6]}-{phone_digits[6:]}"
            )

            user_data = {
                "email": normalized_email,
                "first_name": fname,
                "last_name": lname,
                "date_of_birth": dob_date,
                "phone": formatted_phone,
                "street_address": self.query_one("#reg_addr").value,
                "city": self.query_one("#reg_city").value,
                "province": self.query_one("#reg_prov").value,
                "postal_code": self.query_one("#reg_postal").value,
                "emergency_first_name": self.query_one("#reg_em_fname").value,
                "emergency_last_name": self.query_one("#reg_em_lname").value,
                "emergency_phone": self.query_one("#reg_em_phone").value,
                "allergies": self.query_one("#reg_allergies").value,
                "health_concerns": self.query_one("#reg_health").value,
                "interests": self.query_one("#reg_interests").value,
                "skills_training": self.query_one("#reg_skills").value,
                "account_comments": self.query_one("#reg_comments").value,
            }

            # Only check agreements in non-staff mode (staff mode handles manually in popup)
            if not self.staff_mode:
                user_data["policies_agreed"] = self.query_one("#reg_policies").value
                user_data["code_of_conduct_agreed"] = self.query_one("#reg_code").value

                if not (
                    user_data["policies_agreed"] and user_data["code_of_conduct_agreed"]
                ):
                    self.app.notify("You must agree to the policies.", severity="error")
                    return

            if self.staff_mode:
                # STAFF MODE: Launch confirmation screen
                self.app.push_screen(
                    StaffConfirmScreen(user_data, p1),
                    self.on_staff_confirm_complete,
                )
            else:
                # NORMAL MODE: Register as pending
                services.register_user(user_data, p1)
                self.app.pop_screen()
                self.app.notify(
                    "Registration Successful! Please wait for staff approval."
                )

        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")

    def on_staff_confirm_complete(self, result: bool):
        """Callback from StaffConfirmScreen. If true, registration finished."""
        if result:
            self.app.pop_screen()  # Close the register screen
