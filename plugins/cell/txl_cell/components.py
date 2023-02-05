from functools import partial

import pkg_resources
import y_py as Y
from asphalt.core import Component, Context
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from txl.base import Cell, CellFactory, Kernel, Widgets
from txl.hooks import register_component

YDOCS = {
    ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="ypywidgets")
}


class Source(Static):
    def __init__(self, cell, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cell = cell

    async def on_click(self):
        if self.cell.kernel:
            await self.cell.kernel.execute(self.cell.ydoc, self.cell.ycell)


class CellMeta(type(Cell), type(Container)):
    pass


class _Cell(Cell, Container, metaclass=CellMeta):
    def __init__(
        self,
        ycell: Y.YMap,
        ydoc: Y.YDoc,
        language: str | None,
        kernel: Kernel | None,
        widgets: Widgets | None,
    ) -> None:
        super().__init__()
        self.styles.height = "auto"
        self.ycell = ycell
        self.ydoc = ydoc
        self.language = language
        self.kernel = kernel
        self.widgets = widgets
        self.outputs = []
        self.update()
        self.ycell.observe(self.on_change)

    def on_change(self, event):
        if "execution_count" in event.keys:
            key = event.keys["execution_count"]
            if key["action"] == "update" and key["oldValue"] != key["newValue"]:
                execution_count = self.get_execution_count(key["newValue"])
                self.execution_count.update(execution_count)
        elif "source" in event.keys:
            key = event.keys["source"]
            if key["action"] == "update" and key["oldValue"] != key["newValue"]:
                source = self.get_source(key["newValue"])
                self.source.update(source)
        elif "outputs" in event.keys:
            key = event.keys["outputs"]
            if key["action"] == "update" and key["oldValue"] != key["newValue"]:
                outputs = key["newValue"]
                if not outputs:
                    # cell got re-executed
                    for output in self.outputs:
                        output.remove()
                else:
                    # outputs can only append
                    i = len(key["oldValue"])
                    for output in key["newValue"][i:]:
                        output_widget = self.get_output_widget(output)
                        self.mount(output_widget)
                        self.outputs.append(output_widget)

    def get_execution_count(self, value):
        execution_count = str(value).removesuffix(".0")
        return f"[green]In [[#66ff00]{execution_count}[/#66ff00]]:[/green]"

    def get_source(self, cell):
        source = "".join(cell["source"])
        theme = "ansi_dark"
        if cell["cell_type"] == "code":
            renderable = Panel(
                Syntax(
                    source,
                    self.language,
                    theme=theme,
                ),
                border_style="yellow",
            )
        elif cell["cell_type"] == "markdown":
            renderable = Markdown(source, code_theme=theme)
        else:
            renderable = Text(source)
        return renderable

    def update(self):
        cell = self.ycell.to_json()
        execution_count = (
            self.get_execution_count(cell["execution_count"])
            if "execution_count" in cell
            else ""
        )
        self.execution_count = Static(execution_count)
        self.mount(self.execution_count)
        source = self.get_source(cell)
        self.source = Source(self, source)
        self.mount(self.source)

        for output in cell.get("outputs", []):
            output_widget = self.get_output_widget(output)
            self.mount(output_widget)
            self.outputs.append(output_widget)

    def get_output_widget(self, output):
        output_type = output["output_type"]
        execution_count = ""
        widget = None
        if output_type == "stream":
            text = "".join(output["text"])
            renderable = Text.from_ansi(text)
        elif output_type == "error":
            text = "\n".join(output["traceback"]).rstrip()
            renderable = Text.from_ansi(text)
        elif output_type == "execute_result":
            execution_count = output.get("execution_count", " ") or " "
            execution_count = Text.from_markup(
                f"[red]Out[[#ee4b2b]{execution_count}[/#ee4b2b]]:[/red]\n"
            )
            if "application/vnd.jupyter.ywidget-view+json" in output["data"]:
                model_id = output["data"]["application/vnd.jupyter.ywidget-view+json"][
                    "model_id"
                ]
                if model_id in self.widgets.widgets:
                    model = self.widgets.widgets[model_id]["model"]
                    widget = YDOCS[f"txl_{model.name}"](model)
            if not widget:
                data = output["data"].get("text/plain", "")
                renderable = Text()
                if isinstance(data, list):
                    text = "".join(data)
                    renderable += Text.from_ansi(text)
                else:
                    text = data
                    renderable += Text.from_ansi(text)
        else:
            output_widget = Static("Error: cannot render output")

        if widget is None:
            output_widget = Static(renderable)
        else:
            output_widget = widget
        return output_widget


class CellComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        widgets = await ctx.request_resource(Widgets, "widgets")
        cell_factory = partial(_Cell, widgets=widgets)
        ctx.add_resource(cell_factory, name="cell", types=CellFactory)


c = register_component("cell", CellComponent)
