import json
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union
from urllib import parse

import httpx
import y_py as Y
from asphalt.core import Component, Context
from jupyter_ydoc import ydocs
from txl.base import Contents
from txl.hooks import register_component
from websockets import connect
from ypy_websocket import WebsocketProvider


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
        self,
        base_url: str,
        query_params: Dict[str, List[str]],
        cookies: httpx.Cookies,
        collaborative: bool,
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies
        self.collaborative = collaborative

    async def get(self, path: str, is_dir: bool = False, on_change: Optional[Callable] = None) -> Union[List, str]:
        path = "" if path == "." else path
        if is_dir or not self.collaborative:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.base_url}/api/contents/{path}",
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
        else:
            # it's a collaborative document
            doc_format = "json" if path.endswith(".ipynb") else "text"
            doc_type = "notebook" if path.endswith(".ipynb") else "file"
            async with httpx.AsyncClient() as client:
                r = await client.put(
                    f"{self.base_url}/api/yjs/roomid/{path}",
                    json={"format": doc_format, "type": doc_type},
                )
            roomid = r.text
            ws_url = f"ws{self.base_url[self.base_url.find(':'):]}/api/yjs/{roomid}"
            ws_cookies = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            ydoc = Y.YDoc()
            jupyter_ydoc = ydocs[doc_type](ydoc)
            if on_change:
                jupyter_ydoc.observe(partial(self.on_change, jupyter_ydoc, on_change))
            self.websocket = await connect(ws_url, extra_headers=[("Cookie", ws_cookies)])
            # AT_EXIT.append(self.websocket.close)
            WebsocketProvider(ydoc, self.websocket)
            if doc_type == "notebook":
                return {}
            else:
                return ""
                
        if type == "directory":
            dir_list = [Entry(entry) for entry in content]
            return sorted(dir_list, key=lambda entry: (not entry.is_dir(), entry.name))
        else:
            return document

    def on_change(self, jupyter_ydoc, on_change: Callable, events) -> None:
        content = jupyter_ydoc.get()
        on_change(content)


class ContentsComponent(Component):

    def __init__(self, url: str = "http://127.0.0.1:8000", collaborative: bool = True):
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

c = register_component("contents", ContentsComponent, enable=False)
