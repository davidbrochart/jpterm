from functools import partial

from asphalt.core import Component, Context
from textual.containers import Container
from textual.events import Event
from textual.keys import Keys

from txl.base import Contents, Editor, Editors, FileOpenEvent
from txl.text_input import TextInput


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
        self.ytext = await self.contents.get(path, type="file")
        self.editor = TextInput(ytext=self.ytext._ysource, path=path)
        self.mount(self.editor)

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.ControlS:
            await self.contents.save(self.path, self.ytext)
            event.stop()


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
