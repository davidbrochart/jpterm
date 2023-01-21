from asphalt.core import Component, Context
from rich.syntax import Syntax
from rich.traceback import Traceback
from textual.widgets import Static

from txl.base import Contents, Editor, Editors, FileOpenEvent
from txl.hooks import register_component


class TextViewerMeta(type(Editor), type(Static)):
    pass


class TextViewer(Editor, Static, metaclass=TextViewerMeta):

    text: str
    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__(expand=True)
        self.contents = contents

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="unicode")
        self.text = self.ytext.source
        self.update_viewer()
        self.ytext.observe(self.on_change)

    def update_viewer(self):
        try:
            lexer = Syntax.guess_lexer(self.path, code=self.text)
            syntax = Syntax(
                self.text,
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
            self.sub_title = self.path

    def on_mount(self):
        self.expand

    def on_change(self, target, event):
        self.text = self.ytext.source
        self.update_viewer()


class TextViewerComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")

        def text_viewer_factory():
            return TextViewer(contents)

        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(text_viewer_factory)
        else:
            text_viewer = text_viewer_factory()
            ctx.add_resource(text_viewer, name="text_viewer", types=Editor)


c = register_component("text_viewer", TextViewerComponent)
