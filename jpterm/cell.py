from typing import Any, Dict, Optional
from uuid import uuid4


class Cell:

    json: Dict[str, Any]

    def __init__(self, notebook, cell_json: Optional[Dict[str, Any]] = None):
        self.notebook = notebook
        self.json = cell_json or empty_cell_json()

    async def run(self):
        self.clear_outputs()
        if self.json["cell_type"] != "code":
            return
        # it's a code cell
        if not self.source.strip():
            return
        # the cell is not empty
        await self.notebook.run_cell(self)

    @property
    def source(self):
        return "".join(self.json["source"])

    def clear_outputs(self):
        if self.json["outputs"]:
            self.notebook.dirty = True
            if self.json["cell_type"] == "code":
                self.json["outputs"] = []

def empty_cell_json():
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "source": [],
        "outputs": [],
    }
