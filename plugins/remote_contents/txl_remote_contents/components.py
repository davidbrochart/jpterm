import asyncio
import base64
import json
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union
from urllib import parse

import httpx
import y_py as Y
from asphalt.core import Component, Context
from httpx_ws import aconnect_ws
from jupyter_ydoc import ydocs
from txl.base import Contents
from txl.hooks import register_component
from ypy_websocket import WebsocketProvider


class Websocket:
    def __init__(self, websocket, roomid: str):
        self.websocket = websocket
        self.roomid = roomid

    @property
    def path(self) -> str:
        return self.roomid

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            message = await self.recv()
        except BaseException:
            raise StopAsyncIteration()
        return message

    async def send(self, message: bytes):
        await self.websocket.send_bytes(message)

    async def recv(self) -> bytes:
        return await self.websocket.receive_bytes()


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
        i = base_url.find(":")
        self.ws_url = ("wss" if base_url[i - 1] == "s" else "ws") + base_url[i:]

    async def get(
        self,
        path: str,
        is_dir: bool = False,
        type: str = "text",
        on_change: Optional[Callable] = None,
    ) -> Union[List, str, bytes, Dict[str, Any]]:
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
            if model["type"] == "file":
                document = model["content"]
            elif model["type"] == "notebook":
                document = model["content"]
                if isinstance(model["content"], (str, bytes)):
                    document = json.loads(model["content"])
            elif model["type"] == "directory":
                dir_list = [Entry(entry) for entry in model["content"]]
                document = sorted(
                    dir_list, key=lambda entry: (not entry.is_dir(), entry.name)
                )
            if model["format"] == "base64":
                document = document.encode()
                document = base64.b64decode(document)
            return document

        else:
            # it's a collaborative document
            doc_format = "json" if path.endswith(".ipynb") else "text"
            doc_type = "notebook" if path.endswith(".ipynb") else "file"
            async with httpx.AsyncClient() as client:
                r = await client.put(
                    f"{self.base_url}/api/yjs/roomid/{path}",
                    json={"format": doc_format, "type": doc_type},
                    params={**self.query_params},
                    cookies=self.cookies,
                )
            self.cookies.update(r.cookies)
            roomid = r.text
            ydoc = Y.YDoc()
            jupyter_ydoc = ydocs[doc_type](ydoc)
            if on_change:
                jupyter_ydoc.observe(partial(self.on_change, jupyter_ydoc, on_change))
            asyncio.create_task(self._websocket_provider(roomid, ydoc))
            if doc_type == "notebook":
                return {}
            else:
                return ""

    async def _websocket_provider(self, roomid, ydoc):
        ws_url = f"{self.ws_url}/api/yjs/{roomid}"
        async with aconnect_ws(ws_url, cookies=self.cookies) as websocket:
            WebsocketProvider(ydoc, Websocket(websocket, roomid))
            await asyncio.Future()

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
