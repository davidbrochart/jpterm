import asyncio
import fcntl
import os
import pty
import shlex
import struct
import termios

from asphalt.core import Component, Context
from textual.widget import Widget
from textual.widgets._header import HeaderTitle

from txl.base import Header, Launcher, TerminalFactory, Terminals
from txl.hooks import register_component


class TerminalsMeta(type(Terminals), type(Widget)):
    pass


class LocalTerminals(Terminals, Widget, metaclass=TerminalsMeta):
    def __init__(self, header: Header, terminal: TerminalFactory):
        self.header = header
        self.terminal = terminal
        self._send_queue = asyncio.Queue()
        self._recv_queue = asyncio.Queue()
        self._data_or_disconnect = None
        self._event = asyncio.Event()
        super().__init__()

    async def open(self):
        terminal = self.terminal(self._recv_queue, self._send_queue)
        terminal.focus()
        await self.mount(terminal)
        terminal.set_size(self.size)
        self._ncol = self.size.width
        self._nrow = self.size.height
        self._fd = self._open_terminal()
        self._p_out = os.fdopen(self._fd, "w+b", 0)
        asyncio.create_task(self._run())
        asyncio.create_task(self._send())
        self.header.query_one(HeaderTitle).text = "Terminal"

    def _open_terminal(self):
        pid, fd = pty.fork()
        if pid == 0:
            argv = shlex.split("bash")
            env = dict(
                TERM="linux",
                LC_ALL="en_GB.UTF-8",
                COLUMNS=str(self._ncol),
                LINES=str(self._nrow),
            )
            os.execvpe(argv[0], argv, env)
        return fd

    async def _run(self):
        loop = asyncio.get_running_loop()

        def on_output():
            try:
                self._data_or_disconnect = self._p_out.read(65536).decode()
                self._event.set()
            except Exception:
                loop.remove_reader(self._p_out)
                self._data_or_disconnect = None
                self._event.set()

        loop.add_reader(self._p_out, on_output)
        await self._send_queue.put(["setup", {}])
        while True:
            msg = await self._recv_queue.get()
            if msg[0] == "stdin":
                self._p_out.write(msg[1].encode())
            elif msg[0] == "set_size":
                winsize = struct.pack("HH", msg[1], msg[2])
                fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)

    async def _send(self):
        while True:
            await self._event.wait()
            self._event.clear()
            if self._data_or_disconnect is None:
                await self._send_queue.put(["disconnect", 1])
            else:
                await self._send_queue.put(["stdout", self._data_or_disconnect])


class LocalTerminalsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header, "header")
        terminal = await ctx.request_resource(TerminalFactory, "terminal")
        launcher = await ctx.request_resource(Launcher, "launcher")

        def terminals_factory():
            return LocalTerminals(header, terminal)

        launcher.register("terminal", terminals_factory)
        ctx.add_resource(terminals_factory, name="terminals", types=Terminals)


c = register_component("terminals", LocalTerminalsComponent)
