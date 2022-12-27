import asyncio
import json
from typing import Dict, List

import httpx
import websockets
from asphalt.core import Component, Context
from textual.widget import Widget
from textual.widgets._header import HeaderTitle
from txl.base import TerminalFactory, Terminals, Header, Launcher
from txl.hooks import register_component
from urllib import parse


class TerminalsMeta(type(Terminals), type(Widget)):
    pass


class RemoteTerminals(Terminals, Widget, metaclass=TerminalsMeta):

    def __init__(
        self,
        base_url: str,
        query_params: Dict[str, List[str]],
        cookies: httpx.Cookies,
        header: Header,
        terminal: TerminalFactory,
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies
        self.header = header
        self.terminal = terminal
        i = base_url.find(":")
        self.ws_url = ("wss" if base_url[i - 1] == "s" else "ws") + base_url[i:]
        self._recv_queue = asyncio.Queue()
        self._send_queue = asyncio.Queue()
        super().__init__()

    async def open(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/terminals",
                json={"cwd": ""},
                #cookies=self.cookies,
            )
            #self.cookies.update(response.cookies)
            name = response.json()["name"]
            response = await client.get(
                f"{self.base_url}/api/terminals",
                cookies=self.cookies,
            )
        if name in [terminal["name"] for terminal in response.json()]:
            terminal = self.terminal(self._send_queue, self._recv_queue)
            terminal.focus()
            await self.mount(terminal)
            terminal.set_size(self.size)
            self.websocket = await websockets.connect(f"{self.ws_url}/terminals/websocket/{name}")
            asyncio.create_task(self._recv())
            asyncio.create_task(self._send())
        self.header.query_one(HeaderTitle).text = "Terminal"

    async def _send(self):
        while True:
            message = await self._send_queue.get()
            await self.websocket.send(json.dumps(message))

    async def _recv(self):
        while True:
            try:
                message = await self.websocket.recv()
            except BaseException:
                break
            await self._recv_queue.put(json.loads(message))


class RemoteTerminalsComponent(Component):

    def __init__(self, url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.url = url

    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header, "header")
        terminal = await ctx.request_resource(TerminalFactory, "terminal")
        launcher = await ctx.request_resource(Launcher, "launcher")
        parsed_url = parse.urlparse(self.url)
        base_url = parse.urljoin(self.url, parsed_url.path).rstrip("/")
        query_params = parse.parse_qs(parsed_url.query)
        cookies = httpx.Cookies()
        def terminals_factory():
            return RemoteTerminals(base_url, query_params, cookies, header, terminal)
        launcher.register("terminal", terminals_factory)
        ctx.add_resource(terminals_factory, name="terminals", types=Terminals)

c = register_component("terminals", RemoteTerminalsComponent)
