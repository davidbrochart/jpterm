import json
from os import scandir
from pathlib import Path
from typing import List, Union

import in_n_out as ino
import y_py as Y
from jupyter_ydoc import ydocs

from txl.base import Contents


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


def contents() -> Contents:
    return LocalContents()


ino.register_provider(contents)
