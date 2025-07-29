from anyio import create_task_group, sleep
from anyioutils import create_task
from fps import Module
from textual._context import active_app
from textual.app import App
from textual.containers import Container
from textual.widgets import MarkdownViewer as TextualMarkdownViewer

from txl.base import Contents, Editor, Editors


class MarkdownViewerMeta(type(Editor), type(Container)):
    pass


class MarkdownViewer(Editor, Container, metaclass=MarkdownViewerMeta):
    def __init__(self, contents: Contents, task_group) -> None:
        super().__init__()
        self.contents = contents
        self.task_group = task_group
        self.viewer = None

    async def open(self, path: str) -> None:
        self.ytext = await self.contents.get(path, type="file")
        self.focus()
        await self._update_viewer()
        self.ytext.observe(self.on_change)

    async def _update_viewer(self):
        md = self.ytext.source
        if self.viewer is not None:
            self.viewer.remove()
        self.viewer = TextualMarkdownViewer(md, show_table_of_contents=True)
        self.mount(self.viewer)

    def on_change(self, target, event):
        create_task(self.update_viewer(), self.task_group)


class MarkdownViewerModule(Module):
    def __init__(self, name: str, register: bool = True):
        super().__init__(name)
        self.register = register

    async def start(self) -> None:
        contents = await self.get(Contents)
        app = await self.get(App)

        async with create_task_group() as self.tg:
            def markdown_viewer_factory():
                active_app.set(app)
                return MarkdownViewer(contents, self.tg)

            if self.register:
                editors = await self.get(Editors)
                editors.register_editor_factory(markdown_viewer_factory, [".md"])
            else:
                markdown_viewer = markdown_viewer_factory()
                self.put(markdown_viewer, Editor)

            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        self.tg.cancel_scope.cancel()
