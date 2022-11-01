from pathlib import Path

from asphalt.core import Component, Context
from textual.binding import Binding
from textual.containers import Container
from txl.base import CellFactory, Editor, Editors, Contents, FileOpenEvent
from txl.hooks import register_component


class NotebookEditorMeta(type(Editor), type(Container)):
    pass


class NotebookEditor(Editor, Container, metaclass=NotebookEditorMeta):

    def __init__(
        self,
        contents: Contents,
        cell_factory: CellFactory,
    ) -> None:
        super().__init__(id="editor")
        self.contents = contents
        self.cell_factory = cell_factory

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        nb = await self.contents.get_content(path)

        for cell in nb["cells"]:
            source = "".join(cell["source"])
            self.mount(self.cell_factory(source))

    def get_bindings(self):
        return [Binding(key="b", action="insert_cell_below", description="Insert cell below")]
    
    def action_insert_cell_below(self):
        pass


class NotebookEditorComponent(Component):

    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        cell_factory = await ctx.request_resource(CellFactory, "cell_factory")
        def notebook_editor_factory():
            return NotebookEditor(contents, cell_factory)
        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(notebook_editor_factory, [".ipynb"])
        else:
            notebook_editor = notebook_editor_factory()
            ctx.add_resource(notebook_editor, name="notebook_editor", types=Editor)


c = register_component("notebook_editor", NotebookEditorComponent)
