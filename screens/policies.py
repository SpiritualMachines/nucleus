from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, Markdown


class PolicyScreen(Screen):
    """A reusable modal screen to display text files."""

    def __init__(self, title: str, file_path: str):
        super().__init__()
        self.policy_title = title
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        with Container(classes="splash-container"):
            yield Label(self.policy_title, classes="title")

            with VerticalScroll(classes="splash-content"):
                yield Markdown(self.load_text())

            yield Button("Close", variant="primary", id="close_policy")

    def load_text(self) -> str:
        try:
            # UPDATED PATH: theme/policies/
            with open(f"theme/policies/{self.file_path}", "r") as f:
                return f.read()
        except FileNotFoundError:
            return f"# Error\nCould not find file: theme/policies/{self.file_path}"

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "close_policy":
            self.app.pop_screen()
