from functools import partial

from asphalt.core import Component, Context
from textual.containers import VerticalScroll
from textual.events import Event
from textual.keys import Keys

from txl.base import CellFactory, Contents, Editor, Editors, FileOpenEvent, Kernels


class NotebookEditorMeta(type(Editor), type(VerticalScroll)):
    pass


class NotebookEditor(Editor, VerticalScroll, metaclass=NotebookEditorMeta):
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
        self.cells = []
        self.cell_i = 0

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.ynb = await self.contents.get(path, type="notebook")
        self.update()
        self.ynb.observe(self.on_change)

    def update(self):
        ipynb = self.ynb.source
        self.language = (
            ipynb.get("metadata", {}).get("kernelspec", {}).get("language", "")
        )
        if self.kernel is None:
            kernel_name = ipynb.get("metadata", {}).get("kernelspec", {}).get("name")
            if kernel_name:
                self.kernel = self.kernels(kernel_name)
        for i_cell in range(self.ynb.cell_number):
            cell = self.cell_factory(
                self.ynb._ycells[i_cell], self.ynb.ydoc, self.language, self.kernel
            )
            self.mount(cell)
            self.cells.append(cell)

    def on_change(self, target, event):
        if target == "cells":
            for e in event:
                e.path()[0]

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.Up:
            event.stop()
            if self.cell_i > 0:
                self.current_cell.unselect()
                self.cell_i -= 1
                self.current_cell.select()
                self.scroll_to_widget(self.current_cell)
        elif event.key == Keys.Down:
            event.stop()
            if self.cell_i < len(self.cells) - 1:
                self.current_cell.unselect()
                self.cell_i += 1
                self.current_cell.select()
                self.scroll_to_widget(self.current_cell)
        elif event.key == Keys.Return or event.key == Keys.Enter:
            event.stop()
            self.current_cell.source.focus()
        elif event.key == Keys.Space:
            event.stop()
            if self.kernel:
                await self.kernel.execute(self.ynb.ydoc, self.ynb._ycells[self.cell_i])

    def on_click(self) -> None:
        for cell_i, cell in enumerate(self.cells):
            if cell.clicked:
                cell.clicked = False
                cell.select()
                self.cell_i = cell_i
            elif cell.selected:
                cell.unselect()

    @property
    def current_cell(self):
        return self.cells[self.cell_i]


class NotebookEditorComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)
        kernels = await ctx.request_resource(Kernels)
        cell_factory = await ctx.request_resource(CellFactory)

        notebook_editor_factory = partial(
            NotebookEditor, contents, kernels, cell_factory
        )

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(notebook_editor_factory, [".ipynb"])
        else:
            notebook_editor = notebook_editor_factory()
            ctx.add_resource(notebook_editor, types=Editor)
