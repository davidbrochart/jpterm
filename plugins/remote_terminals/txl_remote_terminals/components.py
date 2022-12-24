import asyncio
import json
from typing import Dict, List

import httpx
import pyte
import websockets
from asphalt.core import Component, Context
from rich.console import RenderableType
from rich.text import Text
from textual.containers import Container
from textual import events
from textual.widget import Widget
from textual.widgets._header import HeaderTitle
from txl.base import Terminals, Header
from txl.hooks import register_component
from urllib import parse


CTRL_KEYS = {
    "left": "\u001b[D",
    "right": "\u001b[C",
    "up": "\u001b[A",
    "down": "\u001b[B",
}


class PyteDisplay:
    def __init__(self, lines):
        self.lines = lines

    def __rich_console__(self, console, options):
        for line in self.lines:
            yield line


class TerminalsWidget(Widget, can_focus=True):
    def __init__(self, send_queue, recv_queue, ncol, nrow):
        self.recv_queue = recv_queue
        self.send_queue = send_queue
        self.nrow = nrow
        self.ncol = ncol
        self._display = PyteDisplay([Text()])
        self._screen = pyte.Screen(ncol, nrow)
        self.stream = pyte.Stream(self._screen)
        asyncio.create_task(self.recv())
        super().__init__()
        self.focus()

    def render(self) -> RenderableType:
        return self._display

    async def on_key(self, event: events.Key) -> None:
        char = CTRL_KEYS.get(event.key) or event.character
        await self.send_queue.put(["stdin", char])

    async def recv(self):
        while True:
            message = await self.recv_queue.get()
            cmd = message[0]
            if cmd == "setup":
                await self.send_queue.put(["set_size", self.nrow, self.ncol, 567, 573])
            elif cmd == "stdout":
                chars = message[1]
                self.stream.feed(chars)
                lines = []
                for i, line in enumerate(self._screen.display):
                    text = Text.from_ansi(line)
                    x = self._screen.cursor.x
                    if i == self._screen.cursor.y and x < len(text):
                        cursor = text[x]
                        cursor.stylize("reverse")
                        new_text = text[:x]
                        new_text.append(cursor)
                        new_text.append(text[x + 1:])
                        text = new_text
                    lines.append(text)
                self._display = PyteDisplay(lines)
                self.refresh()


class TerminalsMeta(type(Terminals), type(Container)):
    pass


class RemoteTerminals(Terminals, Container, metaclass=TerminalsMeta):

    def __init__(
        self,
        base_url: str,
        query_params: Dict[str, List[str]],
        cookies: httpx.Cookies,
        header: Header,
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies
        self.header = header
        i = base_url.find(":")
        self.ws_url = ("wss" if base_url[i - 1] == "s" else "ws") + base_url[i:]
        self.ncol = 80
        self.nrow = 24
        self.recv_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
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
            self.websocket = await websockets.connect(f"{self.ws_url}/terminals/websocket/{name}")
            self.widget = TerminalsWidget(self.send_queue, self.recv_queue, self.ncol, self.nrow)
            self.mount(self.widget)
            asyncio.create_task(self._recv())
            asyncio.create_task(self._send())
        self.header.query_one(HeaderTitle).text = "Terminal"

    async def _send(self):
        while True:
            message = await self.send_queue.get()
            await self.websocket.send(json.dumps(message))

    async def _recv(self):
        while True:
            try:
                message = await self.websocket.recv()
            except BaseException:
                break
            await self.recv_queue.put(json.loads(message))


class RemoteTerminalsComponent(Component):

    def __init__(self, url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.url = url

    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header, "header")
        parsed_url = parse.urlparse(self.url)
        base_url = parse.urljoin(self.url, parsed_url.path).rstrip("/")
        query_params = parse.parse_qs(parsed_url.query)
        cookies = httpx.Cookies()
        def terminals_factory():
            return RemoteTerminals(base_url, query_params, cookies, header)
        ctx.add_resource(terminals_factory, name="terminals", types=Terminals)

c = register_component("terminals", RemoteTerminalsComponent)
