from typing import Dict, List, Union

import httpx


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


class Contents:

    base_url: str
    query_params: Dict[str, List[str]]
    cookies: httpx.Cookies

    def __init__(
        self, base_url: str, query_params: Dict[str, List[str]], cookies: httpx.Cookies
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies

    async def get_content(self, path: str) -> Union[List, str]:
        if path == ".":
            path = ""
        else:
            path = f"/{path}"
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/contents{path}",
                params={**{"content": 1}, **self.query_params},
                cookies=self.cookies,
            )
        self.cookies.update(r.cookies)
        model = r.json()
        type = model["type"]
        if type == "directory":
            dir_list = [Entry(entry) for entry in model["content"]]
            return sorted(dir_list, key=lambda entry: (not entry.is_dir(), entry.name))
        elif type in ("file", "notebook"):
            return model["content"]
        else:
            return ""
