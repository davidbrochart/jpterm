from functools import partial

from asphalt.core import Component, Context
from rich.syntax import Syntax
from rich.traceback import Traceback
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from txl.base import Contents, Editor, Editors, FileOpenEvent


class TextViewerMeta(type(Editor), type(Static)):
    pass


class Viewer(Static):
    DEFAULT_CSS = """
    Viewer {
        width: auto;
        height: auto;
    }
    """

    def _update(self, path, text):
        try:
            lexer = Syntax.guess_lexer(path, code=text)
            syntax = Syntax(
                text,
                lexer=lexer,
                line_numbers=True,
                word_wrap=False,
                indent_guides=True,
                theme="github-dark",
            )
        except Exception:
            self.update(Traceback(theme="github-dark", width=None))
        else:
            self.update(syntax)
            self.sub_title = path


class TextViewer(Editor, Container, metaclass=TextViewerMeta):
    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__()
        self.contents = contents
        self.viewer = Viewer(expand=True, shrink=False)

    def compose(self) -> ComposeResult:
        yield self.viewer

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="file")
        self.viewer._update(path, self.ytext.source)
        self.ytext.observe(self.on_change)

    def on_mount(self):
        self.expand

    def on_change(self, target, event):
        self.viewer._update(self.path, self.ytext.source)


class TextViewerComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)

        text_viewer_factory = partial(TextViewer, contents)

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(text_viewer_factory)
        else:
            ctx.add_resource(text_viewer_factory(), types=Editor)
