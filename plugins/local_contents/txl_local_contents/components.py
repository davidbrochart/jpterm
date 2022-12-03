import json
from os import scandir
from pathlib import Path
from typing import Callable, List, Optional, Union

from asphalt.core import Component, Context
from txl.base import Contents
from txl.hooks import register_component


class LocalContents(Contents):

    async def get(self, path: str, is_dir: bool = False, on_change: Optional[Callable] = None) -> Union[List, str]:
        p = Path(path)
        assert p.is_dir() == is_dir
        if p.is_dir():
            return sorted(
                list(scandir(path)), key=lambda entry: (not entry.is_dir(), entry.name)
            )
        elif p.is_file():
            text = p.read_text()
            if p.suffix == ".ipynb":
                return json.loads(text)
            return text
        else:
            return ""

    def on_change(self, jupyter_ydoc, on_change: Callable, events) -> None:
        pass


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
