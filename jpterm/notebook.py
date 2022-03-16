import json
from typing import List

from .cell import Cell


class Notebook:

    cells: List[Cell]

    def __init__(self, api=None, path=None):
        self.api = api
        self.path = path
        self.json = None
        self.cells = []
        self.kd = None

    async def open(self):
        text = await self.api.contents.get_content(self.path)
        self.json = json.loads(text)
        self.cells = [Cell(notebook=self, cell_json=cell_json) for cell_json in self.json["cells"]]
        self.kd = self.api.kernels.KernelDriver(kernel_name="python3", session_type="notebook", session_name=self.path)
        await self.kd.start()

    async def run_cell(self, cell: Cell):
        await self.kd.execute(cell.source)

    async def run_all(self):
        for cell in self.cells:
            await cell.run()

    async def close(self):
        await self.kd.stop()
