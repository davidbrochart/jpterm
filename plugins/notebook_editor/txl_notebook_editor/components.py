import asyncio
import json
from functools import partial
from typing import Any

import anyio
import pkg_resources
from asphalt.core import Component, Context
from httpx import AsyncClient
from textual.containers import VerticalScroll
from textual.events import Event
from textual.keys import Keys
from textual.widgets import Select

from txl.base import (
    CellFactory,
    Contents,
    Editor,
    Editors,
    FileOpenEvent,
    Kernels,
    Kernelspecs,
    Launcher,
    MainArea,
)

ydocs = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyter_ydoc")}


class NotebookEditorMeta(type(Editor), type(VerticalScroll)):
    pass


class NotebookEditor(Editor, VerticalScroll, metaclass=NotebookEditorMeta):
    def __init__(
        self,
        contents: Contents,
        kernels: Kernels,
        kernelspecs: dict[str, Any],
        cell_factory: CellFactory,
        main_area: MainArea,
        experimental: bool = False,
    ) -> None:
        super().__init__()
        self.contents = contents
        self.kernels = kernels
        self.kernelspecs = kernelspecs
        self.cell_factory = cell_factory
        self.main_area = main_area
        self.experimental = experimental
        self.kernel = None
        self.cells = []
        self.cell_i = 0
        self.cell_copy = None
        self.edit_mode = False
        self.nb_change_target = asyncio.Queue()
        self.nb_change_events = asyncio.Queue()

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def select_kernel(self) -> str:
        select = Select((name, name) for name in self.kernelspecs["kernelspecs"])

        kernel_selected = [anyio.Event()]
        def on_kernel_select():
            kernel_selected[0].set()

        select.watch_value = on_kernel_select
        self.mount(select)
        while True:
            await kernel_selected[0].wait()
            if select.value != Select.BLANK:
                break
            kernel_selected[0] = anyio.Event()
        select.remove()
        return select.value

    async def get_untitled(self, path: str = ".") -> str:
        dir_list = [dir_entry.name for dir_entry in await self.contents.get(path, is_dir=True)]
        i = 0
        while True:
            s = str(i) if i > 0 else ""
            name = f"Untitled{s}.ipynb"
            if name not in dir_list:
                return name
            i += 1

    async def create_empty_notebook(self, kernel_name: str) -> str:
        kernel = self.kernelspecs["kernelspecs"][kernel_name]
        path = await self.get_untitled()
        ynb = ydocs["notebook"]()
        ynb.set(
            {
                "cells": [],
                "metadata": {
                    "kernelspec": {
                        "display_name": kernel["spec"]["display_name"],
                        "language": kernel["spec"]["language"],
                        "name": kernel_name,
                    }
                },
            }
        )
        await self.contents.save(path, ynb)
        return path

    async def open(self, path: str | None = None) -> None:
        if path is None:
            kernel_name = await self.select_kernel()
            path = await self.create_empty_notebook(kernel_name)
            self.main_area.set_label(path)
        self.path = path
        self.ynb = await self.contents.get(self.path, type="notebook", format="json")
        self.update()
        self.ynb.observe(self.on_change)
        asyncio.create_task(self.observe_nb_changes())

    def update(self):
        ipynb = self.ynb.source
        self.language = ipynb.get("metadata", {}).get("kernelspec", {}).get("language", None)
        if self.kernel is None:
            kernel_name = ipynb.get("metadata", {}).get("kernelspec", {}).get("name")
            if kernel_name:
                self.kernel = self.kernels(kernel_name)
        for i_cell in range(self.ynb.cell_number):
            cell = self.cell_factory(
                self.ynb.ycells[i_cell], self.language, self.kernel
            )
            self.mount(cell)
            self.cells.append(cell)
        if self.cells:
            self.cells[self.cell_i].select()

    def on_change(self, target, events):
        self.nb_change_target.put_nowait(target)
        self.nb_change_events.put_nowait(events)

    async def observe_nb_changes(self):
        while True:
            target = await self.nb_change_target.get()
            events = await self.nb_change_events.get()
            if target == "meta":
                for event in events:
                    meta = event.target
                    kernelspec = meta.get("metadata", {}).get("kernelspec", {})
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
                    if event.path:
                        continue
                    idx = 0
                    for d in event.delta:
                        retain = d.get("retain")
                        if retain is not None:
                            idx += retain
                        delete = d.get("delete")
                        if delete is not None:
                            self.cells[idx].remove()
                            del self.cells[idx]
                        insert = d.get("insert")
                        if insert is not None:
                            for c in insert:
                                ycell = c
                                cell = self.cell_factory(ycell, self.language, self.kernel)
                                if not self.cells:
                                    self.mount(cell)
                                else:
                                    if idx < len(self.cells):
                                        self.mount(cell, before=self.cells[idx])
                                    else:
                                        self.mount(cell, after=self.cells[idx - 1])
                                    if idx < self.cell_i:
                                        self.cell_i += 1
                                self.cells.insert(idx, cell)
                                idx += 1

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
                self.current_cell.unselect()
                self.ynb.ycells.move(self.cell_i, self.cell_i - 1)
                async def do_later():
                    if self.cell_i > 1:
                        self.cell_i -= 2
                    self.current_cell.select()
                    self.current_cell.focus()
                    self.scroll_to_widget(self.current_cell)
                asyncio.create_task(do_later())
        elif event.key == Keys.ControlDown:
            event.stop()
            if self.cell_i < len(self.cells) - 1:
                self.current_cell.unselect()
                self.ynb.ycells.move(self.cell_i, self.cell_i + 2)
                async def do_later():
                    self.cell_i += 1
                    self.current_cell.select()
                    self.current_cell.focus()
                    self.scroll_to_widget(self.current_cell)
                asyncio.create_task(do_later())
        elif event.key == Keys.ControlS:
            await self.contents.save(self.path, self.ynb)
            event.stop()
        elif event.key == Keys.Return or event.key == Keys.Enter:
            event.stop()
            self.current_cell.source.focus()
            self.edit_mode = True
        elif event.character == "a":
            event.stop()
            ycell = self.ynb.create_ycell(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "source": "",
                }
            )
            self.ynb.ycells.insert(self.cell_i, ycell)
        elif event.character == "b":
            event.stop()
            ycell = self.ynb.create_ycell(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "source": "",
                }
            )
            self.ynb.ycells.insert(self.cell_i + 1, ycell)
        elif event.character == "l":
            event.stop()
            del self.current_cell.ycell["outputs"][:]
        elif event.character == "c":
            event.stop()
            self.cell_copy = str(self.current_cell.ycell)
        elif event.character == "x":
            event.stop()
            self.cell_copy = str(self.current_cell.ycell)
            del self.ynb.ycells[self.cell_i]
        elif event.key == Keys.ControlV:
            event.stop()
            if self.cell_copy is not None:
                ycell = self.ynb.create_ycell(json.loads(self.cell_copy))
                self.ynb.ycells[self.cell_i:self.cell_i] = [ycell]
        elif event.character == "v":
            event.stop()
            if self.cell_copy is not None:
                ycell = self.ynb.create_ycell(json.loads(self.cell_copy))
                cell_i = self.cell_i + 1
                self.ynb.ycells[cell_i:cell_i] = [ycell]
        elif event.key == Keys.ControlE:
            event.stop()
            if self.kernel:
                if self.experimental:
                    async with AsyncClient() as http:
                        await http.post(
                            f"{self.contents.base_url}/api/kernels/{self.kernel.kernel.kernel_id}/execute",
                            json={
                                "document_id": self.contents.document_id[self.ynb],
                                #"cell_idx": self.cell_i,
                                "cell_id": self.current_cell.ycell["id"],
                            }
                        )
                else:
                    await self.kernel.execute(self.current_cell.ycell)
        elif event.key == Keys.ControlR:
            event.stop()
            if self.kernel:
                if self.experimental:
                    async with AsyncClient() as http:
                        await http.post(
                            f"{self.contents.base_url}/api/kernels/{self.kernel.kernel.kernel_id}/execute",
                            json={
                                "document_id": self.contents.document_id[self.ynb],
                                #"cell_idx": self.cell_i,
                                "cell_id": self.current_cell.ycell["id"],
                            }
                        )
                else:
                    await self.kernel.execute(self.current_cell.ycell)
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
    def __init__(self, register: bool = True, experimental: bool = False):
        super().__init__()
        self.register = register
        self.experimental = experimental

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)
        kernels = await ctx.request_resource(Kernels)
        kernelspecs = await ctx.request_resource(Kernelspecs)
        cell_factory = await ctx.request_resource(CellFactory)
        launcher = await ctx.request_resource(Launcher)
        main_area = await ctx.request_resource(MainArea)

        _kernelspecs = await kernelspecs.get()

        notebook_editor_factory = partial(
            NotebookEditor,
            contents,
            kernels,
            _kernelspecs,
            cell_factory,
            main_area,
            self.experimental,
        )

        launcher.register("notebook", notebook_editor_factory)

        if self.register:
            editors = await ctx.request_resource(Editors)
            editors.register_editor_factory(notebook_editor_factory, [".ipynb"])
        else:
            notebook_editor = notebook_editor_factory()
            ctx.add_resource(notebook_editor, types=Editor)
