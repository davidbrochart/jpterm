from functools import partial

from asphalt.core import Component, Context
from rich.syntax import Syntax
from textual.containers import Container

from txl.base import Contents, Editor, Editors, FileOpenEvent
from txl.text_input import ScrollableTextInput


class _Editor(ScrollableTextInput):
    def __init__(self, path, ydoc, ytext):
        lexer = Syntax.guess_lexer(path, code=str(ytext))
        super().__init__(lexer=lexer, ydoc=ydoc, ytext=ytext)


class TextEditorMeta(type(Editor), type(Container)):
    pass


class TextEditor(Editor, Container, metaclass=TextEditorMeta):

    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__()
        self.contents = contents

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="unicode")
        self.editor = _Editor(path, ydoc=self.ytext.ydoc, ytext=self.ytext._ysource)
        self.mount(self.editor)


class TextEditorComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)

        text_editor_factory = partial(TextEditor, contents)

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(text_editor_factory)
        else:
            ctx.add_resource(text_editor_factory, types=Editor)
