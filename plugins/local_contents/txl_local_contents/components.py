import json
from os import scandir
from typing import List, Union

import pkg_resources
from anyio import Path
from asphalt.core import Component, Context
from pycrdt import Doc

from txl.base import Contents

ydocs = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyter_ydoc")}


class LocalContents(Contents):
    async def get(
        self,
        path: str,
        is_dir: bool = False,
        type: str = "file",
        format: str | None = None,
    ) -> Union[List, Doc]:
        p = Path(path)
        assert (await p.is_dir()) == is_dir
        if await p.is_dir():
            return sorted(list(scandir(path)), key=lambda entry: (not entry.is_dir(), entry.name))
        if await p.is_file():
            jupyter_ydoc = ydocs[type]()
            if type == "file":
                jupyter_ydoc.source = await p.read_text()
            elif type == "blob":
                jupyter_ydoc.source = await p.read_bytes()
            elif type == "notebook":
                jupyter_ydoc.source = json.loads(await p.read_text())
        return jupyter_ydoc

    async def save(
        self,
        path: str,
        jupyter_ydoc: Doc,
    ) -> None:
        p = Path(path)
        source = jupyter_ydoc.source
        if isinstance(source, dict):
            await p.write_text(json.dumps(source, indent=2))
        elif isinstance(source, bytes):
            await p.write_bytes(source)
        else:
            await p.write_text(source)


class LocalContentsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = LocalContents()
        ctx.add_resource(contents, types=Contents)
