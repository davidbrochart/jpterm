from anyio import Event
from fps import Module
from textual._context import active_app
from textual.app import App
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
    cli: bool = False

    def __init__(self, header, footer, main_area, *args, **kwargs):
        self.header = header
        self.footer = footer
        self.main_area = main_area
        self.shell_ready = Event()
        super().__init__(*args, **kwargs)

    def start(self, launcher, file_browser) -> None:
        self.launcher = launcher
        self.file_browser = file_browser
        self.shell_ready.set()

    async def on_mount(self) -> None:
        if self.cli:
            return
        await self.shell_ready.wait()
        active_app.set(self)
        await self.mount(self.header)
        container = Container(self.file_browser, self.main_area)
        await self.mount(container)
        await self.mount(self.footer)
        self.main_area.show(self.launcher, "Launcher", mount=False)

    def watch_show_browser(self, show_browser: bool) -> None:
        self.set_class(show_browser, "-show-browser")

    def action_toggle_files(self) -> None:
        self.show_browser = not self.show_browser

    def action_open_launcher(self) -> None:
        self.main_area.show(self.launcher, "Launcher")


class JptermModule(Module):
    def __init__(self, name: str, driver_class=None):
        super().__init__(name)
        self.driver_class = driver_class

    async def start(self) -> None:
        header = _Header()
        footer = _Footer()
        main_area = _MainArea()
        self.put(header, Header)
        self.put(footer, Footer)
        self.put(main_area, MainArea)
        jpterm = Jpterm(
            header,
            footer,
            main_area,
            driver_class=self.driver_class,
        )
        self.put(jpterm, App)
        launcher = await self.get(Launcher)
        file_browser = await self.get(FileBrowser)
        editors = await self.get(Editors)
        file_browser.open_file_signal.connect(editors.on_open)
        jpterm.start(launcher, file_browser)
