from asphalt.core import Component, Context
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import var

from txl.base import Editors, FileBrowser, Footer, Header, Launcher, MainArea
from txl.hooks import register_component

from .footer import Footer as _Footer
from .header import Header as _Header
from .main_area import MainArea as _MainArea


class Jpterm(App):

    CSS_PATH = "jpterm.css"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("l", "open_launcher", "Open Launcher"),
        ("q", "quit", "Quit"),
    ]
    show_browser = var(True)

    def __init__(
        self,
        header,
        footer,
        main_area,
        file_browser,
        editors,
        launcher,
        *args,
        **kwargs
    ):
        self.header = header
        self.footer = footer
        self.main_area = main_area
        self.file_browser = file_browser
        self.editors = editors
        self.launcher = launcher
        super().__init__(*args, **kwargs)

    def watch_show_browser(self, show_browser: bool) -> None:
        self.set_class(show_browser, "-show-browser")

    def compose(self) -> ComposeResult:
        yield self.header
        self.main_area.show(self.launcher)
        yield Container(
            self.file_browser,
            self.main_area,
        )
        yield self.footer

    def action_toggle_files(self) -> None:
        self.show_browser = not self.show_browser

    def action_open_launcher(self) -> None:
        self.main_area.show(self.launcher)


class JptermComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = _Header()
        footer = _Footer()
        main_area = _MainArea()
        ctx.add_resource(header, name="header", types=Header)
        ctx.add_resource(footer, name="footer", types=Footer)
        ctx.add_resource(main_area, name="main_area", types=MainArea)
        file_browser = await ctx.request_resource(FileBrowser, "file_browser")
        editors = await ctx.request_resource(Editors, "editors")
        file_browser.open_file_signal.connect(editors.on_open)
        launcher = await ctx.request_resource(Launcher, "launcher")
        jpterm = Jpterm(
            header,
            footer,
            main_area,
            file_browser,
            editors,
            launcher,
        )
        ctx.add_resource(jpterm, name="app", types=App)


c = register_component("app", JptermComponent)
