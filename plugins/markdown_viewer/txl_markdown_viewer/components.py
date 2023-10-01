import asyncio

from asphalt.core import Component, Context
from textual.containers import Container
from textual.widgets import MarkdownViewer as TextualMarkdownViewer

from txl.base import Contents, Editor, Editors, FileOpenEvent


class MarkdownViewerMeta(type(Editor), type(Container)):
    pass


class MarkdownViewer(Editor, Container, metaclass=MarkdownViewerMeta):
    def __init__(self, contents: Contents) -> None:
        self.contents = contents
        self.viewer = None
        super().__init__()

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.ytext = await self.contents.get(path, type="file")
        self.focus()
        await self.update_viewer()
        self.ytext.observe(self.on_change)

    async def update_viewer(self):
        md = self.ytext.source
        if self.viewer is not None:
            self.viewer.remove()
        self.viewer = TextualMarkdownViewer(md, show_table_of_contents=True)
        self.mount(self.viewer)

    def on_change(self, target, event):
        asyncio.create_task(self.update_viewer())


class MarkdownViewerComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)

        def markdown_viewer_factory():
            return MarkdownViewer(contents)

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(markdown_viewer_factory, [".md"])
        else:
            markdown_viewer = markdown_viewer_factory()
            ctx.add_resource(markdown_viewer, types=Editor)
