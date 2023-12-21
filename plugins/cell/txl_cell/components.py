import asyncio
import json
from functools import partial

import pkg_resources
from asphalt.core import Component, Context
from pycrdt import Doc, Map, MapEvent, Text
from rich.text import Text as RichText
from textual.containers import Container
from textual.widgets import Static

from txl.base import Cell, CellFactory, Contents, Kernel, Widgets
from txl.text_input import TextInput

YDOCS = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="ypywidgets")}


class Source(TextInput):
    def __init__(self, ycell, show_border: bool = True, *args, **kwargs):
        super().__init__(ytext=ycell["source"], *args, **kwargs)
        self.show_border = show_border
        self.clicked = False
        self._selected = False
        self.set_styles(css="height: auto; max-height: 100%;")
        self.is_code = ycell["cell_type"] == "code"
        if self.is_code and show_border:
            self.set_styles(css="border: round yellow;")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        if self.show_border:
            if value:
                if self.is_code:
                    self.set_styles(css="border: double yellow;")
            else:
                if self.is_code:
                    self.set_styles(css="border: round yellow;")


class CellMeta(type(Cell), type(Container)):
    pass


class _Cell(Cell, Container, metaclass=CellMeta, can_focus=True):
    def __init__(
        self,
        ycell: Map,
        language: str | None,
        kernel: Kernel | None,
        contents: Contents | None,
        widgets: Widgets | None,
        show_execution_count: bool = True,
        show_border: bool = True,
    ) -> None:
        super().__init__()
        self.ycell = ycell
        self._language = language
        self.kernel = kernel
        self.contents = contents
        self.widgets = widgets
        self.show_execution_count = show_execution_count
        self.show_border = show_border
        self.outputs = []
        self.update()
        self.ycell.observe_deep(self.on_change)
        self.styles.height = "auto"
        self.cell_change_events = asyncio.Queue()
        self.widget_change_events = asyncio.Queue()
        self.tasks = [
            asyncio.create_task(self.observe_cell_changes()),
            asyncio.create_task(self.observe_widget_changes()),
        ]

    def on_click(self):
        self.clicked = True

    def on_change(self, events):
        self.cell_change_events.put_nowait(events)

    def on_widget_change(self, ydoc, event):
        self.widget_change_events.put_nowait((ydoc, event))

    async def observe_widget_changes(self):
        while True:
            ydoc, event = await self.widget_change_events.get()
            model_name = event.delta[0]["insert"]
            model = YDOCS[f"{model_name}Model"](ydoc=ydoc)
            widget = YDOCS[f"txl_{model_name}"](model)
            self.mount(widget)
            self.outputs.append(widget)

    async def observe_cell_changes(self):
        while True:
            events = await self.cell_change_events.get()
            for event in events:
                if isinstance(event, MapEvent):
                    if "execution_state" in event.keys:
                        if self.show_execution_count:
                            key = event.keys["execution_state"]
                            if key["newValue"] == "busy":
                                execution_count = self.get_execution_count("*")
                                self.execution_count.update(execution_count)
                    if "execution_count" in event.keys:
                        if self.show_execution_count:
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
                else:
                    if event.path:
                        if event.path[0] == "outputs":
                            for d in event.delta:
                                if "delete" in d:
                                    for output in self.outputs:
                                        output.remove()
                                elif "insert" in d:
                                    is_widget = False
                                    if len(event.path) == 1:
                                        inserted = d["insert"][0]
                                        if isinstance(inserted, Doc):
                                            # this is a widget
                                            is_widget = True
                                            room_id = f"ywidget:{inserted.guid}"
                                            asyncio.create_task(self.contents.websocket_provider(
                                                room_id, inserted
                                            ))
                                            inserted["_model_name"] = model_name = Text()
                                            model_name.observe(partial(
                                                self.on_widget_change, inserted
                                            ))
                                        else:
                                            #output = json.loads(str(inserted))
                                            output = inserted
                                    else:
                                        _output = self.ycell["outputs"][event.path[1]]
                                        key = event.path[2]
                                        output = json.loads(str(_output))
                                        output[key] = d["insert"][0]
                                    if is_widget:
                                        pass
                                    else:
                                        output_widget = self.get_output_widget(output)
                                        self.mount(output_widget)
                                        self.outputs.append(output_widget)

    def get_execution_count(self, value):
        execution_count = " " if value is None else str(value).removesuffix(".0")
        return f"[green]In [[#66ff00]{execution_count}[/#66ff00]]:[/green]"

    def update(self):
        cell = json.loads(str(self.ycell))
        if self.show_execution_count:
            execution_state = self.ycell.get("execution_state")
            if execution_state != "busy":
                execution_count = (
                    self.get_execution_count(self.ycell.get("execution_count", ""))
                )
            else:
                execution_count = (
                    self.get_execution_count("*")
                )
            self.execution_count = Static(execution_count)
            self.mount(self.execution_count)
        cell_type = cell["cell_type"]
        if cell_type == "markdown":
            language = "markdown"
        elif cell_type == "code":
            language = self.language
        else:
            language = None
        self.source = Source(
            ycell=self.ycell,
            language=language,
            show_border=self.show_border,
        )
        self.mount(self.source)

        for output in cell.get("outputs", []):
            output_widget = self.get_output_widget(output)
            if output_widget is not None:
                self.mount(output_widget)
                self.outputs.append(output_widget)

    def get_output_widget(self, output):
        if "guid" in output:
            guid = output["guid"]
            ywidget_doc = Doc()
            room_id = f"ywidget:{guid}"
            asyncio.create_task(self.contents.websocket_provider(room_id, ywidget_doc))
            ywidget_doc["_model_name"] = model_name = Text()
            model_name.observe(partial(self.on_widget_change, ywidget_doc))
            return

        output_type = output["output_type"]
        execution_count = ""
        widget = None
        if output_type == "stream":
            text = "".join(output["text"])
            renderable = RichText.from_ansi(text)
        elif output_type == "error":
            text = "\n".join(output["traceback"]).rstrip()
            renderable = RichText.from_ansi(text)
        elif output_type == "execute_result":
            execution_count = output.get("execution_count", " ") or " "
            if execution_count != " ":
                execution_count = int(execution_count)
            execution_count = RichText.from_markup(
                f"[red]Out[[#ee4b2b]{execution_count}[/#ee4b2b]]:[/red]\n"
            )
            if "application/vnd.jupyter.ywidget-view+json" in output["data"]:
                model_id = output["data"]["application/vnd.jupyter.ywidget-view+json"]["model_id"]
                if model_id in self.widgets.widgets:
                    model = self.widgets.widgets[model_id]["model"]
                    widget = YDOCS[f"txl_{model.__class__.__name__[:-5]}"](model)
            if not widget:
                data = output["data"].get("text/plain", "")
                renderable = execution_count
                if isinstance(data, list):
                    text = "".join(data)
                    renderable += RichText.from_ansi(text)
                else:
                    text = data
                    renderable += RichText.from_ansi(text)
        else:
            output_widget = Static("Error: cannot render output")

        if widget is None:
            output_widget = Static(renderable)
        else:
            output_widget = widget
        return output_widget

    def select(self) -> None:
        self.source.selected = True

    def unselect(self) -> None:
        self.source.selected = False

    @property
    def selected(self) -> bool:
        return self.source.selected

    @property
    def clicked(self) -> bool:
        return self.source.clicked

    @clicked.setter
    def clicked(self, value: bool):
        self.source.clicked = value

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, value: str):
        self._language = value
        self.source.language = value


class CellComponent(Component):
    def __init__(self, show_execution_count: bool = True, show_border: bool = True):
        super().__init__()
        self.show_execution_count = show_execution_count
        self.show_border = show_border

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents)
        widgets = await ctx.request_resource(Widgets)
        cell_factory = partial(
            _Cell,
            contents=contents,
            widgets=widgets,
            show_execution_count=self.show_execution_count,
            show_border=self.show_border,
        )
        ctx.add_resource(cell_factory, types=CellFactory)
