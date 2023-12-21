from functools import partial
from typing import Any

import pkg_resources
from asphalt.core import Component, Context
from pycrdt import ArrayEvent, Doc
from textual.containers import VerticalScroll
from textual.events import Event
from textual.keys import Keys
from textual.widgets import Select

from txl.base import CellFactory, Console, Kernels, Kernelspecs, Launcher, MainArea

ydocs = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyter_ydoc")}


class ConsoleMeta(type(Console), type(VerticalScroll)):
    pass


class _Console(Console, VerticalScroll, metaclass=ConsoleMeta):
    def __init__(
        self,
        kernels: Kernels,
        kernelspecs: dict[str, Any],
        cell_factory: CellFactory,
        main_area: MainArea,
    ) -> None:
        super().__init__()
        self.kernels = kernels
        self.kernelspecs = kernelspecs
        self.cell_factory = cell_factory
        self.main_area = main_area
        self.cells = []
        self.cell_i = 0

    async def open(self):
        self.select = Select((name, name) for name in self.kernelspecs["kernelspecs"])
        self.select.watch_value = self.on_select_kernel
        self.mount(self.select)

    def on_select_kernel(self):
        if self.select.value == Select.BLANK:
            return
        self.main_area.set_label("Console")
        self.select.remove()
        kernel = self.kernelspecs["kernelspecs"][self.select.value]
        self.kernel = self.kernels(kernel["name"])
        self.language = kernel["spec"]["language"]
        self.ydoc = Doc()
        self.ynb = ydocs["notebook"](self.ydoc)
        self.ynb.set({"cells": []})
        self.ynb.observe(self.on_change)
        cell = self.cell_factory(
            ycell=self.ynb.ycells[self.cell_i],
            language=self.language,
            kernel=self.kernel,
            show_execution_count=False,
            show_border=False,
        )
        self.mount(cell)
        self.cells.append(cell)
        cell.select()
        self.current_cell.source.focus()

    def on_change(self, target, events):
        if target == "cells":
            for event in events:
                if isinstance(event, ArrayEvent):
                    if len(event.path) < 2:
                        insert = None
                        retain = None
                        for d in event.delta:
                            if "insert" in d:
                                insert = d["insert"]
                            elif "retain" in d:
                                retain = d["retain"]
                        i = 0 if retain is None else retain
                        if insert is not None:
                            for c in insert:
                                cell = self.cell_factory(
                                    ycell=c,
                                    language=self.language,
                                    kernel=self.kernel,
                                    show_execution_count=False,
                                    show_border=False,
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
        if self.cells:
            self.cells[self.cell_i].select()

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.ControlR:
            event.stop()
            if self.kernel:
                await self.kernel.execute(self.current_cell.ycell)
            ycell = self.ynb.create_ycell(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "source": "",
                }
            )
            self.ynb.ycells.append(ycell)
            self.current_cell.unselect()
            self.current_cell.source.can_focus = False
            self.current_cell.source.cursor_blink = False
            self.cell_i += 1
            self.current_cell.select()
            self.current_cell.source.focus()
            self.scroll_to_widget(self.current_cell)

    @property
    def current_cell(self):
        return self.cells[self.cell_i]


class ConsoleComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        main_area = await ctx.request_resource(MainArea)
        kernels = await ctx.request_resource(Kernels)
        kernelspecs = await ctx.request_resource(Kernelspecs)
        cell_factory = await ctx.request_resource(CellFactory)
        launcher = await ctx.request_resource(Launcher)

        _kernelspecs = await kernelspecs.get()

        console_factory = partial(_Console, kernels, _kernelspecs, cell_factory, main_area)

        launcher.register("console", console_factory)
        ctx.add_resource_factory(console_factory, types=Console)
