from asphalt.core import Component, add_resource, request_resource, start_background_task
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import var

from txl.base import Editors, FileBrowser, Footer, Header, Launcher, MainArea

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

    def __init__(self, header, footer, main_area, file_browser, editors, launcher, *args, **kwargs):
        self.header = header
        self.footer = footer
        self.main_area = main_area
        self.file_browser = file_browser
        self.editors = editors
        self.launcher = launcher
        self.main_area.show(self.launcher, "Launcher", mount=False)
        super().__init__(*args, **kwargs)

    def watch_show_browser(self, show_browser: bool) -> None:
        self.set_class(show_browser, "-show-browser")

    def compose(self) -> ComposeResult:
        yield self.header
        yield Container(
            self.file_browser,
            self.main_area,
        )
        yield self.footer

    def action_toggle_files(self) -> None:
        self.show_browser = not self.show_browser

    def action_open_launcher(self) -> None:
        self.main_area.show(self.launcher, "Launcher")


class JptermComponent(Component):
    def __init__(self, driver_class=None):
        super().__init__()
        self.driver_class = driver_class

    async def start(self) -> None:
        header = _Header()
        footer = _Footer()
        main_area = _MainArea()
        await add_resource(header, types=Header)
        await add_resource(footer, types=Footer)
        await add_resource(main_area, types=MainArea)
        file_browser = await request_resource(FileBrowser)
        editors = await request_resource(Editors)

        async def open_file():
            async with file_browser.open_file_signal.stream_events() as stream:
                async for event in stream:
                    await editors.on_open(event)

        await start_background_task(open_file, name="File browser open file")

        launcher = await request_resource(Launcher)
        jpterm = Jpterm(
            header,
            footer,
            main_area,
            file_browser,
            editors,
            launcher,
            driver_class=self.driver_class,
        )
        await add_resource(jpterm, types=App)
