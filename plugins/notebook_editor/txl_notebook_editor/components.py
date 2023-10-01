import json
from functools import partial

import y_py as Y
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
        self.cell_copy = None
        self.edit_mode = False

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        self.path = path
        self.ynb = await self.contents.get(path, type="notebook", format="json")
        self.update()
        self.ynb.observe(self.on_change)

    def update(self):
        ipynb = self.ynb.source
        self.language = (
            ipynb.get("metadata", {}).get("kernelspec", {}).get("language", None)
        )
        if self.kernel is None:
            kernel_name = ipynb.get("metadata", {}).get("kernelspec", {}).get("name")
            if kernel_name:
                self.kernel = self.kernels(kernel_name)
        for i_cell in range(self.ynb.cell_number):
            cell = self.cell_factory(
                self.ynb.ycells[i_cell], self.ynb.ydoc, self.language, self.kernel
            )
            self.mount(cell)
            self.cells.append(cell)
        if self.cells:
            self.cells[self.cell_i].select()

    def on_change(self, target, events):
        if target == "meta":
            for event in events:
                kernelspec = event.target.get("metadata", {}).get("kernelspec", {})
                self.language = kernelspec.get("language", None)
                for cell in self.cells:
                    if cell.ycell["cell_type"] == "code":
                        cell.language = self.language
                if self.kernel is None:
                    kernel_name = kernelspec.get("name")
                    if kernel_name:
                        self.kernel = self.kernels(kernel_name)
        elif target == "cells":
            for event in events:
                if isinstance(event, Y.YArrayEvent):
                    insert = None
                    retain = None
                    delete = None
                    for d in event.delta:
                        if "insert" in d:
                            insert = d["insert"]
                        if "delete" in d:
                            delete = d["delete"]
                        elif "retain" in d:
                            retain = d["retain"]
                    i = 0 if retain is None else retain
                    if insert is not None:
                        for c in insert:
                            cell = self.cell_factory(
                                c, self.ynb.ydoc, self.language, self.kernel
                            )
                            if not self.cells:
                                self.mount(cell)
                            else:
                                if i < len(self.cells):
                                    self.mount(cell, before=self.cells[i])
                                else:
                                    self.mount(cell, after=self.cells[i - 1])
                                if i <= self.cell_i:
                                    self.cell_i += 1
                            self.cells.insert(i, cell)
                            i += 1
                    elif delete is not None:
                        self.cells[i].remove()
                        del self.cells[i]
                        if i < self.cell_i:
                            self.cell_i -= 1
        if self.cells:
            self.cells[self.cell_i].select()

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.Escape:
            self.edit_mode = False
            self.current_cell.focus()
        elif event.key == Keys.Up:
            if not self.edit_mode:
                event.stop()
                if self.cell_i > 0:
                    self.current_cell.unselect()
                    self.cell_i -= 1
                    self.current_cell.select()
                    self.current_cell.focus()
                    self.scroll_to_widget(self.current_cell)
        elif event.key == Keys.Down:
            if not self.edit_mode:
                event.stop()
                if self.cell_i < len(self.cells) - 1:
                    self.current_cell.unselect()
                    self.cell_i += 1
                    self.current_cell.select()
                    self.current_cell.focus()
                    self.scroll_to_widget(self.current_cell)
        elif event.key == Keys.ControlUp:
            event.stop()
            if self.cell_i > 0:
                cell_copy = self.current_cell.ycell.to_json()
                ycell = self.ynb.create_ycell(json.loads(cell_copy))
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.insert(t, self.cell_i - 1, ycell)
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.delete(t, self.cell_i)
                self.cell_i -= 2
                self.current_cell.select()
                self.current_cell.focus()
                self.scroll_to_widget(self.current_cell)
                # FIXME: move_to doesn't seem to create an event
                # with self.ynb.ydoc.begin_transaction() as t:
                #     self.ynb.ycells.move_to(t, self.cell_i, self.cell_i + 1)
        elif event.key == Keys.ControlDown:
            event.stop()
            if self.cell_i < len(self.cells) - 1:
                cell_copy = self.current_cell.ycell.to_json()
                ycell = self.ynb.create_ycell(json.loads(cell_copy))
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.insert(t, self.cell_i + 2, ycell)
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.delete(t, self.cell_i)
                self.current_cell.unselect()
                self.cell_i += 1
                self.current_cell.select()
                self.current_cell.focus()
                self.scroll_to_widget(self.current_cell)
                # FIXME: move_to doesn't seem to create an event
                # with self.ynb.ydoc.begin_transaction() as t:
                #     self.ynb.ycells.move_to(t, self.cell_i, self.cell_i + 1)
        elif event.key == Keys.ControlS:
            await self.contents.save(self.path, self.ynb)
            event.stop()
        elif event.key == Keys.Return or event.key == Keys.Enter:
            event.stop()
            self.current_cell.source.focus()
            self.edit_mode = True
        elif event.character == "a":
            event.stop()
            with self.ynb.ydoc.begin_transaction() as t:
                ycell = self.ynb.create_ycell(
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "source": "",
                    }
                )
                self.ynb.ycells.insert(t, self.cell_i, ycell)
        elif event.character == "b":
            event.stop()
            with self.ynb.ydoc.begin_transaction() as t:
                ycell = self.ynb.create_ycell(
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "source": "",
                    }
                )
                self.ynb.ycells.insert(t, self.cell_i + 1, ycell)
        elif event.character == "l":
            event.stop()
            with self.ynb.ydoc.begin_transaction() as t:
                self.current_cell.ycell.set(t, "outputs", [])
        elif event.character == "c":
            event.stop()
            self.cell_copy = self.current_cell.ycell.to_json()
        elif event.character == "x":
            event.stop()
            self.cell_copy = self.current_cell.ycell.to_json()
            with self.ynb.ydoc.begin_transaction() as t:
                self.ynb.ycells.delete(t, self.cell_i)
        elif event.key == Keys.ControlV:
            event.stop()
            if self.cell_copy is not None:
                ycell = self.ynb.create_ycell(json.loads(self.cell_copy))
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.insert(t, self.cell_i, ycell)
        elif event.character == "v":
            event.stop()
            if self.cell_copy is not None:
                ycell = self.ynb.create_ycell(json.loads(self.cell_copy))
                with self.ynb.ydoc.begin_transaction() as t:
                    self.ynb.ycells.insert(t, self.cell_i + 1, ycell)
        elif event.key == Keys.ControlE:
            event.stop()
            if self.kernel:
                await self.kernel.execute(self.ynb.ydoc, self.current_cell.ycell)
        elif event.key == Keys.ControlR:
            event.stop()
            if self.kernel:
                await self.kernel.execute(self.ynb.ydoc, self.current_cell.ycell)
            if self.cell_i < len(self.cells) - 1:
                self.current_cell.unselect()
                self.cell_i += 1
                self.current_cell.select()
                self.current_cell.source.focus()
                self.edit_mode = True
                self.scroll_to_widget(self.current_cell)

    def on_click(self) -> None:
        for cell_i, cell in enumerate(self.cells):
            if cell.clicked:
                cell.clicked = False
                cell.select()
                self.edit_mode = True
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
