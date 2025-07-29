from anyio import create_task_group, sleep
from anyioutils import Queue
from fps import Module
from textual._context import active_app
from textual.app import App
from textual.containers import Container
from textual.events import Event
from textual.keys import Keys

from txl.base import Contents, Editor, Editors, MainArea
from txl.text_input import TextInput


class TextEditorMeta(type(Editor), type(Container)):
    pass


class TextEditor(Editor, Container, metaclass=TextEditorMeta):
    contents: Contents
    path: str

    def __init__(self, contents: Contents, main_area: MainArea, task_group) -> None:
        super().__init__()
        self.contents = contents
        self.main_area = main_area
        self.task_group = task_group
        self.change_target = Queue()
        self.change_events = Queue()

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="file")
        self.editor = TextInput(ytext=self.ytext._ysource, path=path)
        self.task_group.start_soon(self.editor.start)
        self.mount(self.editor)
        self.ytext.observe(self.on_change)
        self.task_group.start_soon(self.observe_changes)

    async def close(self) -> None:
        await self.editor.stop()

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


class TextEditorModule(Module):
    def __init__(self, name: str, register: bool = True):
        super().__init__(name)
        self.register = register

    async def start(self) -> None:
        contents = await self.get(Contents)
        main_area = await self.get(MainArea)
        app = await self.get(App)

        async with create_task_group() as tg:

            class TextEditorFactory:
                def __init__(self):
                    self.text_editors = []

                def __call__(self):
                    active_app.set(app)
                    text_editor = TextEditor(contents, main_area, tg)
                    self.text_editors.append(text_editor)
                    return text_editor

                async def stop(self):
                    async with create_task_group() as tg:
                        for text_editor in self.text_editors:
                            tg.start_soon(text_editor.close)

            self.text_editor_factory = TextEditorFactory()

            if self.register:
                editors = await self.get(Editors)
                editors.register_editor_factory(self.text_editor_factory)
            else:
                self.put(self.text_editor_factory, Editor)

            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        await self.text_editor_factory.stop()
