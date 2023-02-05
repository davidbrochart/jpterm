from typing import Optional, Tuple

from asphalt.core import Component, Context
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.widgets import DataTable

from txl.base import Contents, Editor, Editors, FileOpenEvent, Kernels, Widgets
from txl.hooks import register_component


def _line_range(
    head: Optional[int], tail: Optional[int], num_lines: int
) -> Optional[Tuple[int, int]]:
    if head and tail:
        raise RuntimeError("cannot specify both head and tail")
    if head:
        line_range = (1, head)
    elif tail:
        start_line = num_lines - tail + 2
        finish_line = num_lines + 1
        line_range = (start_line, finish_line)
    else:
        line_range = None
    return line_range


class NotebookViewerMeta(type(Editor), type(DataTable)):
    pass


class NotebookViewer(Editor, DataTable, metaclass=NotebookViewerMeta):
    def __init__(
        self,
        contents: Contents,
        kernels: Kernels,
        widgets: Widgets,
    ) -> None:
        super().__init__()
        self.contents = contents
        self.kernels = kernels
        self.widgets = widgets
        self.kernel = None
        self._row_to_cell_idx = []
        self._selected_cell_idx = None

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
        self.update_viewer()
        self.ynb.observe(self.on_change)

    def update_viewer(self):
        self.clear()

        self.add_column("", width=10)
        self.add_column("", width=100)

        head = None
        tail = None
        theme = "ansi_dark"

        if self.ynb.cell_number == 0:
            return

        self._row_to_cell_idx = []
        for i_cell in range(self.ynb.cell_number):
            cell = self.ynb.get_cell(i_cell)
            execution_count = (
                f"[green]In [[#66ff00]{cell['execution_count'] or ' '}"
                "[/#66ff00]]:[/green]"
                if "execution_count" in cell
                else ""
            )

            source = "".join(cell["source"])
            num_lines = len(source.splitlines())
            if cell["cell_type"] == "code":
                if execution_count:
                    execution_count = "\n" + execution_count
                line_range = _line_range(head, tail, num_lines)
                renderable = Panel(
                    Syntax(
                        source,
                        self.language,
                        theme=theme,
                        line_numbers=True,
                        indent_guides=True,
                        word_wrap=False,
                        line_range=line_range,
                    ),
                    border_style="dim",
                )
                num_lines += 2
            elif cell["cell_type"] == "markdown":
                renderable = Markdown(source, code_theme=theme, hyperlinks=True)
            else:
                renderable = Text(source)

            self.add_row(execution_count, renderable, height=num_lines)
            self._row_to_cell_idx.append(i_cell)

            for output in cell.get("outputs", []):
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
                        print(
                            f'{output["data"]["application/vnd.jupyter.ywidget-view+json"]=}'
                        )
                        model_id = output["data"][
                            "application/vnd.jupyter.ywidget-view+json"
                        ]["model_id"]
                        print(f"{model_id=}")
                        print(f"{self.widgets.widgets=}")
                        if model_id in self.widgets.widgets:
                            widget = self.widgets.widgets[model_id]["widget"]
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
                    continue

                with open("debug.txt", "at") as f:
                    f.write(f"{widget=}\n")
                if widget is None:
                    num_lines = len(text.splitlines())
                    self.add_row(execution_count, renderable, height=num_lines)
                    self._row_to_cell_idx.append(i_cell)
                else:
                    # it's a widget
                    self.add_row(execution_count, widget, height=10)
                    self._row_to_cell_idx.append(i_cell)

    def on_click(self, event: events.Click) -> None:
        DataTable.on_click(self, event)
        if self.show_cursor and self.cursor_type != "none":
            meta = self.get_style_at(event.x, event.y).meta
            if meta:
                self._selected_cell_idx = self._row_to_cell_idx[meta["row"]]

    def on_change(self, target, event):
        self.update_viewer()

    async def key_e(self) -> None:
        if self.kernel:
            ycell = self.ynb._ycells[self._selected_cell_idx]
            with open("debug.txt", "at") as f:
                f.write(f"executing {ycell=}\n")
            await self.kernel.execute(self.ynb.ydoc, ycell)
            with open("debug.txt", "at") as f:
                f.write("executing done\n")


class NotebookViewerComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        kernels = await ctx.request_resource(Kernels, "kernels")
        widgets = await ctx.request_resource(Widgets, "widgets")

        def notebook_viewer_factory():
            return NotebookViewer(contents, kernels, widgets)

        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(notebook_viewer_factory, [".ipynb"])
        else:
            notebook_viewer = notebook_viewer_factory()
            ctx.add_resource(notebook_viewer, name="notebook_viewer", types=Editor)


c = register_component("notebook_viewer", NotebookViewerComponent)
