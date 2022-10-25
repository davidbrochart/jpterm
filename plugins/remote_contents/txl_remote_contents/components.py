import json
from typing import Any, Dict, List, Union
from urllib import parse

import httpx
from asphalt.core import Component, Context
from txl.base import Contents
from txl.hooks import register_component


class Entry:
    """Provide a scandir-like API"""

    def __init__(self, entry: Dict[str, Any]):
        self.entry = entry

    @property
    def name(self) -> str:
        return self.entry["name"]

    @property
    def path(self) -> str:
        return self.entry["path"]

    def is_dir(self) -> bool:
        return self.entry["type"] == "directory"


class RemoteContents(Contents):

    base_url: str
    query_params: Dict[str, List[str]]
    cookies: httpx.Cookies

    def __init__(
        self, base_url: str, query_params: Dict[str, List[str]], cookies: httpx.Cookies, collaborative: bool
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies
        self.collaborative = collaborative
        self.app = None

    async def get_content(self, path: str, is_dir: bool = False) -> Union[List, str]:
        path = "" if path == "." else f"/{path}"
        if is_dir or not self.collaborative:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.base_url}/api/contents{path}",
                    params={**{"content": 1}, **self.query_params},
                    cookies=self.cookies,
                )
            self.cookies.update(r.cookies)
            model = r.json()
            content = model["content"]
            type = model["type"]
            if type == "file":
                document = content
            elif type == "notebook":
                document = content
                if isinstance(content, (str, bytes)):
                    document = json.loads(content)
                
        if type == "directory":
            dir_list = [Entry(entry) for entry in content]
            return sorted(dir_list, key=lambda entry: (not entry.is_dir(), entry.name))
        else:
            return document


class ContentsComponent(Component):

    def __init__(self, url: str, collaborative: bool = False):
        super().__init__()
        self.url = url
        self.collaborative = collaborative

    async def start(
        self,
        ctx: Context,
    ) -> None:
        parsed_url = parse.urlparse(self.url)
        base_url = parse.urljoin(self.url, parsed_url.path).rstrip("/")
        query_params = parse.parse_qs(parsed_url.query)
        cookies = httpx.Cookies()
        contents = RemoteContents(base_url, query_params, cookies, self.collaborative)
        ctx.add_resource(contents, name="contents", types=Contents)


c = register_component("contents", ContentsComponent)
