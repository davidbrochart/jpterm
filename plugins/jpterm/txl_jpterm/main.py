from pathlib import Path

from anyio import Event
from anytext.app import App
from anytext.binding import Binding
from anytext.containers import Container
from anytext.message import Message
from anytext.reactive import var
from fps import Module

from txl.base import Editors, FileBrowser, Footer, Header, Launcher, MainArea

from .close_tab import ConfirmCloseTab
from .footer import Footer as _Footer
from .header import Header as _Header
from .main_area import MainArea as _MainArea


class JptermView(Container):
    """The complete jpterm interface, mountable in any Anytext application.

    Call start() once its launcher and file browser services are available.
    The host owns the service lifetime and handles Closed to restore its UI.
    """

    DEFAULT_CSS = Path(__file__).with_name("jpterm.css").read_text()
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("l", "open_launcher", "Open Launcher"),
        ("q", "close", "Quit"),
        Binding("ctrl+q", "close", show=False, priority=True),
        Binding("ctrl+w", "close_tab", "Close Tab", priority=True),
    ]
    show_browser = var(True)

    class Closed(Message):
        def __init__(self, view):
            self.view = view
            super().__init__()

        @property
        def control(self):
            return self.view

    def __init__(self, header, footer, main_area, **kwargs):
        self.header = header
        self.footer = footer
        self.main_area = main_area
        self.shell_ready = Event()
        self.closed = Event()
        self.launcher = None
        self.file_browser = None
        self._close_dialog = None
        super().__init__(**kwargs)

    def start(self, launcher, file_browser):
        self.launcher = launcher
        self.file_browser = file_browser
        self.main_area.launcher = launcher
        self.shell_ready.set()

    async def on_mount(self):
        await self.shell_ready.wait()
        await self.mount(
            self.header,
            Container(self.file_browser, self.main_area, classes="jpterm-body"),
            self.footer,
        )
        self.main_area.show(self.launcher, "Launcher", mount=False)

    def watch_show_browser(self, show_browser):
        self.set_class(show_browser, "-show-browser")

    def action_toggle_files(self):
        self.show_browser = not self.show_browser

    def action_open_launcher(self):
        self.main_area.show(self.launcher, "Launcher")

    def action_close(self):
        if not self.closed.is_set():
            self.closed.set()
            self.post_message(self.Closed(self))

    async def action_close_tab(self):
        if self._close_dialog is not None:
            return
        widget = self.main_area.shown
        if widget not in self.main_area.widget_to_tab:
            return
        tab, dirty = self.main_area.widget_to_tab[widget]
        if dirty:
            dialog = ConfirmCloseTab(tab.label_text.removeprefix("+ "))
            self._close_dialog = dialog

            async def confirm(discard):
                self._close_dialog = None
                if discard and self.is_mounted:
                    await self.main_area.close(widget)

            self.app.push_screen(dialog, confirm)
        else:
            await self.main_area.close(widget)

    async def on_unmount(self):
        # A host can remove the view while its confirmation screen is visible.
        if self._close_dialog is not None and self._close_dialog.is_mounted:
            await self._close_dialog.dismiss(False)
        self.closed.set()


class Jpterm(App):
    """Standalone terminal host for JptermView."""

    cli: bool = False

    def __init__(self, header, footer, main_area, *args, **kwargs):
        self.view = JptermView(header, footer, main_area)
        super().__init__(*args, **kwargs)

    def start(self, launcher, file_browser):
        self.view.start(launcher, file_browser)

    async def on_mount(self):
        if not self.cli:
            await self.mount(self.view)

    def on_jpterm_view_closed(self, event):
        if event.view is self.view:
            event.stop()
            self.exit()


class JptermModule(Module):
    def __init__(self, name: str, driver_class=None, embedded: bool = False):
        super().__init__(name)
        self.driver_class = driver_class
        self.embedded = embedded

    async def start(self):
        header = _Header()
        footer = _Footer()
        main_area = _MainArea()
        self.put(header, Header)
        self.put(footer, Footer)
        self.put(main_area, MainArea)
        if self.embedded:
            await self.get(App)  # Wait for the host to publish its app service.
            view = JptermView(header, footer, main_area)
        else:
            jpterm = Jpterm(header, footer, main_area, driver_class=self.driver_class)
            self.put(jpterm, App)
            view = jpterm.view
        self.put(view, JptermView)
        launcher = await self.get(Launcher)
        file_browser = await self.get(FileBrowser)
        editors = await self.get(Editors)
        file_browser.open_file_signal.connect(editors.on_open)
        view.start(launcher, file_browser)
