from functools import partial

from asphalt.core import Component, Context
from textual.containers import Container

from txl.base import CellFactory, Contents, Editor, Editors, FileOpenEvent, Kernels
from txl.hooks import register_component


class NotebookEditorMeta(type(Editor), type(Container)):
    pass


class NotebookEditor(Editor, Container, metaclass=NotebookEditorMeta):
    def __init__(
        self,
        contents: Contents,
        kernels: Kernels,
        cell_factory: CellFactory,
    ) -> None:
        super().__init__()
        self.contents = contents
        self.kernels = kernels
        self.cell_factory = cell_factory
        self.kernel = None

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.ynb = await self.contents.get(path, type="notebook")
        ipynb = self.ynb.source
        self.language = (
            ipynb.get("metadata", {}).get("kernelspec", {}).get("language", "")
        )
        kernel_name = ipynb.get("metadata", {}).get("kernelspec", {}).get("name")
        if kernel_name:
            self.kernel = self.kernels(kernel_name)
        self.update()

    def update(self):
        for i_cell in range(self.ynb.cell_number):
            cell = self.cell_factory(
                self.ynb._ycells[i_cell], self.ynb.ydoc, self.language, self.kernel
            )
            self.mount(cell)


class NotebookEditorComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        kernels = await ctx.request_resource(Kernels, "kernels")
        cell_factory = await ctx.request_resource(CellFactory, "cell")

        notebook_editor_factory = partial(
            NotebookEditor, contents, kernels, cell_factory
        )

        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(notebook_editor_factory, [".ipynb"])
        else:
            notebook_editor = notebook_editor_factory()
            ctx.add_resource(notebook_editor, name="notebook_editor", types=Editor)


c = register_component("notebook_editor", NotebookEditorComponent)
