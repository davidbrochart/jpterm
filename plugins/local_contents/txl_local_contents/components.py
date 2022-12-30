import json
from os import scandir
from pathlib import Path
from typing import List, Union

import y_py as Y
from asphalt.core import Component, Context
from jupyter_ydoc import ydocs

from txl.base import Contents
from txl.hooks import register_component


class LocalContents(Contents):
    async def get(
        self,
        path: str,
        is_dir: bool = False,
        type: str = "unicode",
    ) -> Union[List, Y.YDoc]:
        p = Path(path)
        assert p.is_dir() == is_dir
        if p.is_dir():
            return sorted(
                list(scandir(path)), key=lambda entry: (not entry.is_dir(), entry.name)
            )
        if p.is_file():
            jupyter_ydoc = ydocs[type]()
            if type == "unicode":
                jupyter_ydoc.source = p.read_text()
            elif type == "blob":
                jupyter_ydoc.source = p.read_bytes()
            elif type == "notebook":
                jupyter_ydoc.source = json.loads(p.read_text())
        return jupyter_ydoc


class ContentsComponent(Component):
    def __init__(self, *args, **kwargs):
        super().__init__()

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = LocalContents()
        ctx.add_resource(contents, name="contents", types=Contents)


c = register_component("contents", ContentsComponent)
