from typing import Optional, Tuple

from asphalt.core import Component, Context
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import DataTable
from txl.base import Editor, Editors, Contents, FileOpenEvent
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

    def __init__(self, contents: Contents) -> None:
        super().__init__(id="editor")
        self.contents = contents

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        nb = await self.contents.get_content(path)

        self.add_column("", width=10)
        self.add_column("", width=100)

        head = None
        tail = None
        lexer = None
        lexer = lexer or nb.get("metadata", {}).get("kernelspec", {}).get("language", "")
        theme="ansi_dark"
        for cell in nb["cells"]:
            if "execution_count" in cell:
                execution_count = f"[green]In [[#66ff00]{cell['execution_count'] or ' '}[/#66ff00]]:[/green]"
            else:
                execution_count = ""

            source = "".join(cell["source"])
            num_lines = len(source.splitlines())
            if cell["cell_type"] == "code":
                if execution_count:
                    execution_count = "\n" + execution_count
                line_range = _line_range(head, tail, num_lines)
                renderable = Panel(
                    Syntax(
                        source,
                        lexer,
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

            for output in cell.get("outputs", []):
                output_type = output["output_type"]
                execution_count = ""
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

                num_lines = len(text.splitlines())
                self.add_row(execution_count, renderable, height=num_lines)



class NotebookViewerComponent(Component):

    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        def notebook_viewer_factory():
            return NotebookViewer(contents)
        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(notebook_viewer_factory, [".ipynb"])
        else:
            notebook_viewer = notebook_viewer_factory()
            ctx.add_resource(notebook_viewer, name="notebook_viewer", types=Editor)


c = register_component("notebook_viewer", NotebookViewerComponent)
