import asyncio
from functools import partial

import in_n_out as ino
from textual.containers import Container
from textual.widgets import MarkdownViewer as TextualMarkdownViewer

from txl.base import Contents, Editor, Editors


class MarkdownViewerMeta(type(Editor), type(Container)):
    pass


class MarkdownViewer(Editor, Container, metaclass=MarkdownViewerMeta):
    def __init__(self, contents: Contents) -> None:
        self.contents = contents
        self.viewer = None
        super().__init__()

    async def open(self, path: str) -> None:
        self.ytext = await self.contents.get(path, type="unicode")
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


def register_markdown_viewer(editors: Editors):
    @ino.inject
    def inner(contents: Contents):
        markdown_viewer_factory = partial(MarkdownViewer, contents)
        editors.register_editor_factory(markdown_viewer_factory, [".md"])

    inner()


ino.register_processor(register_markdown_viewer)
