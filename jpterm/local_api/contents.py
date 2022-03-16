from os import scandir
from pathlib import Path
from typing import List, Union


async def get_content(path: str) -> Union[List, str]:
    p = Path(path)
    if p.is_dir():
        content = sorted(
            list(scandir(path)), key=lambda entry: (not entry.is_dir(), entry.name)
        )
    elif p.is_file():
        content = p.read_text()
    else:
        content = ""
    return content
