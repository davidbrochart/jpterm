from typing import Dict, List
from urllib import parse

import httpx
from anyio import create_task_group, sleep
from anyioutils import Event, Queue, create_task
from fps import Module
from httpx_ws import aconnect_ws
from textual.widget import Widget
from textual.widgets._header import HeaderTitle

from txl.base import Header, Launcher, TerminalFactory, Terminals


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
        task_group,
    ) -> None:
        self.base_url = base_url
        self.query_params = query_params
        self.cookies = cookies
        self.header = header
        self.terminal = terminal
        self.task_group = task_group
        i = base_url.find(":")
        self.ws_url = ("wss" if base_url[i - 1] == "s" else "ws") + base_url[i:]
        self._recv_queue = Queue()
        self._send_queue = Queue()
        self._done = Event()
        super().__init__()

    async def open(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/terminals",
                json={"cwd": ""},
                params={**self.query_params},
                cookies=self.cookies,
            )
            self.cookies.update(response.cookies)
            r = response.json()
            name = r["name"]
            response = await client.get(
                f"{self.base_url}/api/terminals",
                cookies=self.cookies,
            )
            self.cookies.update(response.cookies)
        if name in [terminal["name"] for terminal in response.json()]:
            self.header.query_one(HeaderTitle).text = "Terminal"
            terminal = self.terminal(self._send_queue, self._recv_queue)
            terminal.focus()
            self.mount(terminal)
            await terminal.size_set.wait()
            async with aconnect_ws(
                f"{self.ws_url}/terminals/websocket/{name}", cookies=self.cookies
            ) as self.websocket:
                self.task_group.start_soon(self._recv)
                self.send_task = create_task(self._send(), self.task_group)
                await self._done.wait()

    async def _send(self):
        while True:
            message = await self._send_queue.get()
            try:
                await self.websocket.send_json(message)
            except BaseException:
                self._done.set()
                break

    async def _recv(self):
        while True:
            try:
                message = await self.websocket.receive_json()
            except Exception:
                self.send_task.cancel()
                return
            await self._recv_queue.put(message)


class RemoteTerminalsModule(Module):
    def __init__(self, name: str, url: str = "http://127.0.0.1:8000"):
        super().__init__(name)
        self.url = url

    async def start(self) -> None:
        header = await self.get(Header)
        terminal = await self.get(TerminalFactory)
        launcher = await self.get(Launcher)
        parsed_url = parse.urlparse(self.url)
        base_url = parse.urljoin(self.url, parsed_url.path).rstrip("/")
        query_params = parse.parse_qs(parsed_url.query)
        cookies = httpx.Cookies()

        async with create_task_group() as self.tg:
            def terminals_factory():
                return RemoteTerminals(base_url, query_params, cookies, header, terminal, self.tg)

            launcher.register("terminal", terminals_factory)
            self.put(terminals_factory, Terminals)
            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        self.tg.cancel_scope.cancel()
