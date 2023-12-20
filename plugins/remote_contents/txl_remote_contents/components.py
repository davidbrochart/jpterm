import asyncio
import json
from base64 import b64encode
from typing import Any, Dict, List, Optional, Union
from urllib import parse

import httpx
import pkg_resources
from asphalt.core import Component, Context
from httpx_ws import aconnect_ws
from pycrdt import Doc
from pycrdt_websocket import WebsocketProvider

from txl.base import Contents

ydocs = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyter_ydoc")}


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
        b = await self.websocket.receive_bytes()
        return bytes(b)


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
        self.document_id = {}

    async def get(
        self,
        path: str,
        is_dir: bool = False,
        type: str = "unicode",
        format: Optional[str] = None,
    ) -> Union[List, Doc]:
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
            if model["type"] == "directory":
                dir_list = [Entry(entry) for entry in model["content"]]
                return sorted(dir_list, key=lambda entry: (not entry.is_dir(), entry.name))
            document = model["content"]
            if type == "notebook":
                if isinstance(model["content"], (str, bytes)):
                    # jupyverse doesn't return JSON
                    document = json.loads(model["content"])
            jupyter_ydoc = ydocs[type]()
            jupyter_ydoc.source = document
            return jupyter_ydoc

        else:
            if format is not None:
                pass
            elif type == "blob":
                format = "base64"
            else:
                format = "text"
            doc_type = type  # if type == "notebook" else "file"
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/api/collaboration/session/{path}",
                    json={"format": format, "type": doc_type},
                    params={**self.query_params},
                    cookies=self.cookies,
                )
            self.cookies.update(response.cookies)
            r = response.json()
            room_id = f"{r['format']}:{r['type']}:{r['fileId']}"
            session_id = r["sessionId"]
            ydoc = Doc()
            jupyter_ydoc = ydocs[type](ydoc)
            asyncio.create_task(self.websocket_provider(room_id, ydoc, session_id))
            self.document_id[jupyter_ydoc] = room_id
            return jupyter_ydoc

    async def save(
        self,
        path: str,
        jupyter_ydoc: Doc,
    ) -> None:
        source = jupyter_ydoc.source
        if isinstance(source, dict):
            cnt = source
            fmt = "json"
            typ = "notebook" if path.endswith(".ipynb") else "file"
        elif isinstance(source, bytes):
            cnt = b64encode(source)
            fmt = "base64"
        else:
            cnt = source
            fmt = "text"
            typ = "file"
        content = {
            "content": cnt,
            "format": fmt,
            "path": path,
            "type": typ,
        }
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self.base_url}/api/contents/{path}",
                json=content,
                params={**self.query_params},
                cookies=self.cookies,
            )
        self.cookies.update(r.cookies)

    async def websocket_provider(self, room_id, ydoc, session_id=None):
        ws_url = f"{self.ws_url}/api/collaboration/room/{room_id}"
        params = None if session_id is None else {"sessionId": session_id}
        async with aconnect_ws(
            ws_url, cookies=self.cookies, params=params
        ) as websocket:
            async with WebsocketProvider(ydoc, Websocket(websocket, room_id)):
                await asyncio.Future()


class RemoteContentsComponent(Component):
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
        ctx.add_resource(contents, types=Contents)
