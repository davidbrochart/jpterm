from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmCloseTab(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmCloseTab {
        align: center middle;
        background: $background 60%;
    }
    #close-tab-dialog {
        width: 60;
        max-width: 90%;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $surface;
    }
    #close-tab-buttons {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    #close-tab-buttons Button {
        margin-left: 1;
        min-width: 0;
        padding: 0 1;
    }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title):
        super().__init__()
        self.tab_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="close-tab-dialog"):
            yield Static(f"Close {self.tab_title}?\nUnsaved changes will be lost.", markup=False)
            with Horizontal(id="close-tab-buttons"):
                yield Button("Cancel", id="keep-editing")
                yield Button("Discard changes", variant="error", id="discard-changes")

    def on_mount(self):
        self.query_one("#keep-editing", Button).focus()

    def action_cancel(self):
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "discard-changes")
