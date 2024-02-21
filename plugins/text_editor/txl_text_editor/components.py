import asyncio
from functools import partial

from asphalt.core import Component, Context
from textual.containers import Container
from textual.events import Event
from textual.keys import Keys

from txl.base import Contents, Editor, Editors, FileOpenEvent, MainArea
from txl.text_input import TextInput


class TextEditorMeta(type(Editor), type(Container)):
    pass


class TextEditor(Editor, Container, metaclass=TextEditorMeta):
    contents: Contents
    path: str

    def __init__(self, contents: Contents, main_area: MainArea) -> None:
        super().__init__()
        self.contents = contents
        self.main_area = main_area
        self.change_target = asyncio.Queue()
        self.change_events = asyncio.Queue()

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="file")
        self.editor = TextInput(ytext=self.ytext._ysource, path=path)
        self.ytext.observe(self.on_change)
        asyncio.create_task(self.observe_changes())
        self.mount(self.editor)

    def on_change(self, target, events):
        self.change_target.put_nowait(target)
        self.change_events.put_nowait(events)

    async def observe_changes(self):
        while True:
            target = await self.change_target.get()
            events = await self.change_events.get()
            if target == "state":
                if "dirty" in events.keys:
                    dirty = events.keys["dirty"]["newValue"]
                    if dirty:
                        self.main_area.set_dirty(self)
                    else:
                        self.main_area.clear_dirty(self)
            else:
                self.main_area.set_dirty(self)

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.ControlS:
            await self.contents.save(self.path, self.ytext)
            self.main_area.clear_dirty(self)
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
        main_area = await ctx.request_resource(MainArea)

        text_editor_factory = partial(TextEditor, contents, main_area)

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(text_editor_factory)
        else:
            ctx.add_resource(text_editor_factory, types=Editor)
