import asyncio
import fcntl
import os
import pty
import shlex
import struct
import termios

import pyte
from asphalt.core import Component, Context
from rich.console import RenderableType
from rich.text import Text
from textual.containers import Container
from textual import events
from textual.widget import Widget
from textual.widgets._header import HeaderTitle
from txl.base import Terminals, Header
from txl.hooks import register_component


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


class LocalsTerminal(Terminals, Container, metaclass=TerminalsMeta):

    def __init__(self, header: Header):
        self.header = header
        self.ncol = 80
        self.nrow = 24
        self.data_or_disconnect = None
        self.fd = self.open_terminal()
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.event = asyncio.Event()
        self.recv_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
        super().__init__()

    async def open(self):
        terminals_widget = TerminalsWidget(self.recv_queue, self.send_queue, self.ncol, self.nrow)
        asyncio.create_task(self._run())
        asyncio.create_task(self._send_data())
        self.mount(terminals_widget)
        self.header.query_one(HeaderTitle).text = "Terminal"

    def open_terminal(self):
        pid, fd = pty.fork()
        if pid == 0:
            argv = shlex.split("bash")
            env = dict(TERM="linux", LC_ALL="en_GB.UTF-8", COLUMNS=str(self.ncol), LINES=str(self.nrow))
            os.execvpe(argv[0], argv, env)
        return fd

    async def _run(self):
        loop = asyncio.get_running_loop()

        def on_output():
            try:
                self.data_or_disconnect = self.p_out.read(65536).decode()
                self.event.set()
            except Exception:
                loop.remove_reader(self.p_out)
                self.data_or_disconnect = None
                self.event.set()

        loop.add_reader(self.p_out, on_output)
        await self.send_queue.put(["setup", {}])
        while True:
            msg = await self.recv_queue.get()
            if msg[0] == "stdin":
                self.p_out.write(msg[1].encode())
            elif msg[0] == "set_size":
                winsize = struct.pack("HH", msg[1], msg[2])
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    async def _send_data(self):
        while True:
            await self.event.wait()
            self.event.clear()
            if self.data_or_disconnect is None:
                await self.send_queue.put(["disconnect", 1])
            else:
                await self.send_queue.put(["stdout", self.data_or_disconnect])


class LocalTerminalsComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header, "header")
        def terminals_factory():
            return LocalsTerminal(header)
        ctx.add_resource(terminals_factory, name="terminals", types=Terminals)

c = register_component("terminals", LocalTerminalsComponent)
