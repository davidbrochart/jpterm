from asphalt.core import Component, Context
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import var
from textual.widgets import Header, Footer
from txl.base import FileBrowser
from txl.hooks import register_component
from txl_editors import Editors


class Jpterm(App):

    CSS_PATH = "jpterm.css"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("q", "quit", "Quit"),
    ]
    show_browser = var(False)

    def __init__(self, *args, **kwargs):
        self.file_browser = kwargs.pop("file_browser")
        self.editors = kwargs.pop("editors")
        super().__init__(*args, **kwargs)

    def watch_show_browser(self, show_browser: bool) -> None:
        self.set_class(show_browser, "-show-browser")

    def compose(self) -> ComposeResult:
        yield Container(
            Header(),
            Vertical(self.file_browser, id="browser-view"),
            Vertical(self.editors, id="editors-view"),
            Footer(),
        )

    def action_toggle_files(self) -> None:
        self.show_browser = not self.show_browser


class JptermComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        file_browser = await ctx.request_resource(FileBrowser, "file_browser")
        editors = await ctx.request_resource(Editors, "editors")
        file_browser.open_file_signal.connect(editors.on_open)
        jpterm = Jpterm(
            file_browser=file_browser,
            editors=editors,
        )
        ctx.add_resource(jpterm, name="app", types=App)


c = register_component("app", JptermComponent)
