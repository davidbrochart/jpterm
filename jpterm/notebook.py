import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .cell import Cell


class Notebook:

    path: Optional[Path]
    json: Optional[Dict]
    cells: List[Cell]
    msgid_to_cell: Dict[str, Cell]

    def __init__(self, api=None, path=None) -> None:
        self.api = api
        self.path = path
        self.json = None
        self.cells = []
        self.msgid_to_cell = {}
        self.kd = None

    async def open(self) -> None:
        text_or_json = await self.api.contents.get_content(self.path)
        if isinstance(text_or_json, Dict):
            # with jupyter-server we get a Dict
            self.json = text_or_json
        else:
            # with jupyverse we get a string
            self.json = json.loads(text_or_json)
        assert self.json is not None
        self.cells = [
            Cell(notebook=self, cell_json=cell_json) for cell_json in self.json["cells"]
        ]
        self.kd = self.api.kernels.KernelDriver(
            kernel_name="python3",
            session_type="notebook",
            session_name=self.path,
            output_hook=self.output_hook,
        )
        assert self.kd is not None
        await self.kd.start()

    async def run_cell(self, cell: Cell):
        assert self.kd is not None
        msg_id = uuid4().hex
        self.msgid_to_cell[msg_id] = cell
        await self.kd.execute(cell.source, msg_id=msg_id)

    async def run_all(self) -> None:
        for cell in self.cells:
            await cell.run()

    async def close(self) -> None:
        assert self.kd is not None
        await self.kd.stop()

    def output_hook(self, msg: Dict[str, Any]):
        msg_id = msg["parent_header"]["msg_id"]
        cell = self.msgid_to_cell[msg_id]
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]
        outputs = cell.json["outputs"]
        if msg_type == "stream":
            if (not outputs) or (outputs[-1]["name"] != content["name"]):
                outputs.append(
                    {"name": content["name"], "output_type": msg_type, "text": []}
                )
            outputs[-1]["text"].append(content["text"])
        elif msg_type in ("display_data", "execute_result"):
            outputs.append(
                {
                    "data": {"text/plain": [content["data"].get("text/plain", "")]},
                    "execution_count": None,
                    "metadata": {},
                    "output_type": msg_type,
                }
            )
        elif msg_type == "error":
            outputs.append(
                {
                    "ename": content["ename"],
                    "evalue": content["evalue"],
                    "output_type": "error",
                    "traceback": content["traceback"],
                }
            )
        else:
            return
