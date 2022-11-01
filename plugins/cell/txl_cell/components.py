from asphalt.core import Component, Context
from textual import events
from textual.keys import Keys
from textual.app import ComposeResult
from textual.widgets import Input, Static
from txl.base import Cell, CellFactory
from txl.hooks import register_component


class CellMeta(type(Cell), type(Static)):
    pass


class _Cell(Cell, Static, metaclass=CellMeta):
    """A cell widget."""

    def __init__(self, *args, **kwargs) -> None:
        self.input_content = kwargs.pop("input_content")
        self.output_content = kwargs.pop("output_content")
        super().__init__(*args, **kwargs)

    def on_key(self, event: events.Key) -> None:
        """Handles key press events when this widget is in focus.
        Pressing "escape" removes focus from this widget.
        Pressing "shift+enter" runs the cell.

        Args:
            event (events.Key): The Key event being handled
        """
        if event.key == Keys.Escape:
            self.screen.set_focus(None)
        elif event.key == "shift+enter":
            self.run()

    def compose(self) -> ComposeResult:
        """Create child widgets of a cell."""
        self.input = Input(self.input_content)
        self.output = Static(self.output_content)
        yield self.input
        yield self.output

    def run(self) -> None:
        self.output.update(f"Run: {self.input.value}")


class CellFactoryComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        def cell_factory(input_content: str = "", output_content: str = "") -> Cell:
            return _Cell(input_content=input_content, output_content=output_content)
        ctx.add_resource(cell_factory, name="cell_factory", types=CellFactory)


c = register_component("cell", CellFactoryComponent)
