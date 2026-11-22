from anyio import create_task_group, sleep
from anytext._context import active_app
from anytext.app import App
from anytext.containers import Container
from anytext.widgets import MarkdownViewer as AnytextMarkdownViewer
from fps import Module

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
        if not getattr(self.app, "cli", False):
            self.ytext.observe(self.on_change)

    async def _update_viewer(self):
        md = self.ytext.source
        if self.viewer is not None:
            await self.viewer.remove()
        self.viewer = AnytextMarkdownViewer(
            show_table_of_contents=not getattr(self.app, "cli", False)
        )
        if getattr(self.app, "cli", False):
            self.viewer.styles.height = "auto"
            self.viewer.styles.overflow_y = "hidden"
            self.viewer.styles.scrollbar_size_vertical = 0
            self.viewer.styles.scrollbar_gutter = "auto"
        await self.mount(self.viewer)
        await self.viewer.document.update(md)

    def on_change(self, target, event):
        self.call_later(self.task_group.start_soon, self._update_viewer)


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
