"""Report export modals for the dashboard."""

__all__ = [
    "CommunityContactsReportModal",
    "PeriodTractionReportModal",
]

from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from core import exporters, services
from screens.directory_select import DirectorySelectScreen


class CommunityContactsReportModal(ModalScreen):
    """
    Modal for exporting all community contact records within a selected date range.
    Mirrors the Period Traction Report flow: date range inputs pre-filled to the
    last 30 days, then CSV or PDF export via the standard directory selector.
    """

    def compose(self) -> ComposeResult:
        today = datetime.now()
        start = today - timedelta(days=30)

        with Vertical(classes="splash-container"):
            yield Label("Community Contacts Report", classes="title")
            yield Label(
                "Select a date range to include in the report.", classes="subtitle"
            )

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(start.strftime("%Y-%m-%d"), id="ccr_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="ccr_end")

            with Horizontal(classes="filter-row"):
                yield Button("Export CSV", variant="success", id="btn_ccr_csv")
                yield Button("Export PDF", variant="primary", id="btn_ccr_pdf")
                yield Button("Cancel", variant="error", id="btn_ccr_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_ccr_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_ccr_csv":
            self._initiate_export("csv")
        elif event.button.id == "btn_ccr_pdf":
            self._initiate_export("pdf")

    def _initiate_export(self, fmt: str):
        def on_directory_selected(path: str | None):
            if path:
                self._run_export(fmt, path)

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def _run_export(self, fmt: str, output_dir: str):
        try:
            start_str = self.query_one("#ccr_start").value.strip()
            end_str = self.query_one("#ccr_end").value.strip()

            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

            data = services.get_community_contacts_report(start_date, end_date)

            if not data["rows"]:
                self.app.notify(
                    "No community contacts in this date range.", severity="warning"
                )
                return

            filename = exporters.get_timestamp_filename(
                "community_contacts_report", fmt
            )

            if fmt == "csv":
                path = exporters.export_to_csv(
                    filename, data["headers"], data["rows"], output_dir
                )
            else:
                period_label = f"{start_str} to {end_str}"
                path = exporters.export_to_pdf(
                    filename,
                    f"Community Contacts Report: {period_label}",
                    data["headers"],
                    data["rows"],
                    output_dir,
                )

            self.app.notify(f"Exported to: {path}")
            self.dismiss(None)

        except ValueError:
            self.app.notify("Invalid date format. Use YYYY-MM-DD.", severity="error")
        except Exception as e:
            self.app.notify(f"Export Failed: {str(e)}", severity="error")


class PeriodTractionReportModal(ModalScreen):
    """
    Modal for generating a Period Traction Report covering all recorded activity
    within a user-selected date range. Includes active memberships, day passes,
    consumable transactions, space sign-ins/outs, and community contact visits.
    The user selects a save directory, then the report is written to CSV or PDF.
    """

    def compose(self) -> ComposeResult:
        today = datetime.now()
        start = today - timedelta(days=30)

        with Vertical(classes="splash-container"):
            yield Label("Generate Period Traction Report", classes="title")
            yield Label(
                "Select a date range to include in the report.", classes="subtitle"
            )

            yield Label("Start Date (YYYY-MM-DD):")
            yield Input(start.strftime("%Y-%m-%d"), id="report_start")

            yield Label("End Date (YYYY-MM-DD):")
            yield Input(today.strftime("%Y-%m-%d"), id="report_end")

            with Horizontal(classes="filter-row"):
                yield Button("Export CSV", variant="success", id="btn_traction_csv")
                yield Button("Export PDF", variant="primary", id="btn_traction_pdf")
                yield Button("Cancel", variant="error", id="btn_traction_cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_traction_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_traction_csv":
            self._initiate_export("csv")
        elif event.button.id == "btn_traction_pdf":
            self._initiate_export("pdf")

    def _initiate_export(self, fmt: str):
        """Opens the directory selector, then runs the export once a path is chosen."""

        def on_directory_selected(path: str | None):
            if path:
                self._run_export(fmt, path)

        self.app.push_screen(DirectorySelectScreen(), on_directory_selected)

    def _run_export(self, fmt: str, output_dir: str):
        """Fetches report data and writes the file in the requested format."""
        try:
            start_str = self.query_one("#report_start").value.strip()
            end_str = self.query_one("#report_end").value.strip()

            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            # Include the full final day by setting time to end of day
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

            data = services.get_period_traction_report_data(start_date, end_date)

            sections = [
                {
                    "title": "Memberships",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Start Date",
                        "End Date",
                        "Description",
                    ],
                    "rows": data["memberships"],
                },
                {
                    "title": "Day Passes",
                    "headers": ["ID", "Name", "Account", "Date", "Description"],
                    "rows": data["day_passes"],
                },
                {
                    "title": "Consumable Transactions",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Type",
                        "Amount",
                        "Date",
                        "Description",
                    ],
                    "rows": data["consumables"],
                },
                {
                    "title": "Sign Ins and Outs",
                    "headers": [
                        "ID",
                        "Name",
                        "Account",
                        "Sign In",
                        "Sign Out",
                        "Visit Type",
                    ],
                    "rows": data["sign_ins"],
                },
                {
                    "title": "Community Contacts",
                    "headers": [
                        "ID",
                        "First Name",
                        "Last Name",
                        "Email",
                        "Phone",
                        "Brought In By",
                        "Visited At",
                        "Community Tour",
                        "Other Reason",
                        "Staff Name and Description",
                    ],
                    "rows": data["community_contacts"],
                },
            ]

            period_label = f"{start_str} to {end_str}"
            filename = exporters.get_timestamp_filename("period_traction_report", fmt)

            if fmt == "csv":
                path = exporters.export_period_report_to_csv(
                    filename, sections, output_dir
                )
            else:
                path = exporters.export_period_report_to_pdf(
                    filename,
                    f"Period Traction Report: {period_label}",
                    sections,
                    output_dir,
                )

            self.app.notify(f"Exported to: {path}")
            self.dismiss(None)

        except ValueError:
            self.app.notify("Invalid date format. Use YYYY-MM-DD.", severity="error")
        except Exception as e:
            self.app.notify(f"Export Failed: {str(e)}", severity="error")
