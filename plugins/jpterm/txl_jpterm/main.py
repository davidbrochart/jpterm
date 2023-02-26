import in_n_out as ino
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


_header = _Header()


def header() -> Header:
    return _header


_footer = _Footer()


def footer() -> Footer:
    return _footer


_main_area = _MainArea()


def main_area() -> MainArea:
    return _main_area


@ino.inject
def jpterm(
    header: Header,
    footer: Footer,
    main_area: MainArea,
    file_browser: FileBrowser,
    launcher: Launcher,
    editors: Editors,
) -> App:
    file_browser.open_file_callbacks.append(editors.on_open)
    return Jpterm(
        header,
        footer,
        main_area,
        file_browser,
        editors,
        launcher,
    )


ino.register_provider(header)
ino.register_provider(footer)
ino.register_provider(main_area)
ino.register_provider(jpterm)
