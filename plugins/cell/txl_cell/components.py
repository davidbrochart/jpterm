from typing import Any, Dict, List

from asphalt.core import Component, Context
from txl.base import Cell, CellFactory
from txl.hooks import register_component


class _Cell(Cell):
    """A cell."""

    def __init__(self, *args, **kwargs) -> None:
        self.source = kwargs.pop("source", [])
        self.outputs = kwargs.pop("outputs", [])

    @property
    def source(self) -> List[str]:
        return self.source

    @source.setter
    def source(self, value: List[str]):
        self.source = value

    @property
    def outputs(self) -> List[Dict[str: Any]]:
        return self.outputs

    @source.setter
    def outputs(self, value: List[Dict[str: Any]]):
        self.outputs = value


class CellFactoryComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        def cell_factory(source: List[str] = "", outputs: List[Dict[str: Any]] = "") -> Cell:
            return _Cell(source=source, outputs=outputs)
        ctx.add_resource(cell_factory, name="cell_factory", types=CellFactory)


c = register_component("cell", CellFactoryComponent)
