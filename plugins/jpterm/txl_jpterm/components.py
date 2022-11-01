from asphalt.core import Component, Context
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import var
from txl.base import FileBrowser, Footer, Header
from txl.hooks import register_component
from txl_editors import Editors

from .footer import Footer as _Footer
from .header import Header as _Header


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
        self.header = kwargs.pop("header")
        self.footer = kwargs.pop("footer")
        super().__init__(*args, **kwargs)

    def watch_show_browser(self, show_browser: bool) -> None:
        self.set_class(show_browser, "-show-browser")

    def compose(self) -> ComposeResult:
        yield Container(
            self.header,
            Vertical(self.file_browser, id="browser-view"),
            Vertical(self.editors, id="editors-view"),
            self.footer,
        )

    def action_toggle_files(self) -> None:
        self.show_browser = not self.show_browser


class JptermComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = _Header()
        footer = _Footer()
        ctx.add_resource(header, name="header", types=Header)
        ctx.add_resource(footer, name="footer", types=Footer)
        file_browser = await ctx.request_resource(FileBrowser, "file_browser")
        editors = await ctx.request_resource(Editors, "editors")
        file_browser.open_file_signal.connect(editors.on_open)
        jpterm = Jpterm(
            header=header,
            footer=footer,
            file_browser=file_browser,
            editors=editors,
        )
        ctx.add_resource(jpterm, name="app", types=App)


c = register_component("app", JptermComponent)
