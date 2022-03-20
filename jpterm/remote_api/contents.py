from typing import List, Union

import httpx

from jpterm.jpterm import BASE_URL, COOKIES


class Entry:
    """Provide a scandir API"""

    def __init__(self, entry):
        self.entry = entry

    @property
    def name(self):
        return self.entry["name"]

    @property
    def path(self):
        return self.entry["path"]

    def is_dir(self):
        return self.entry["type"] == "directory"


async def get_content(path: str) -> Union[List, str]:
    if path == ".":
        path = ""
    else:
        path = f"/{path}"
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}api/contents{path}", params={"content": 1}, cookies=COOKIES
        )
    COOKIES.update(r.cookies)
    model = r.json()
    type = model["type"]
    if type == "directory":
        dir_list = [Entry(entry) for entry in model["content"]]
        return sorted(dir_list, key=lambda entry: (not entry.is_dir(), entry.name))
    elif type in ("file", "notebook"):
        return model["content"]
    else:
        return ""
