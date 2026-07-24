import fcntl
import math
import os
import pty
import shlex
import struct
import termios
from typing import Any

from anyio import Event, create_memory_object_stream, wait_readable
from textual.widget import Widget
from textual.widgets._header import HeaderTitle

from txl.base import Header, TerminalFactory, Terminals
from txl.stapled import StapledObjectStream


class TerminalsMeta(type(Terminals), type(Widget)):
    pass


class LocalTerminals(Terminals, Widget, metaclass=TerminalsMeta):
    def __init__(self, task_group, header: Header, terminal: TerminalFactory):
        self.task_group = task_group
        self.header = header
        self.terminal = terminal
        self._send_queue = StapledObjectStream(
            *create_memory_object_stream[Any](max_buffer_size=math.inf)
        )
        self._recv_queue = StapledObjectStream(
            *create_memory_object_stream[Any](max_buffer_size=math.inf)
        )
        self._data_or_disconnect = None
        self._event = Event()
        super().__init__()

    async def open(self):
        terminal = self.terminal(self._recv_queue, self._send_queue)
        terminal.focus()
        self.mount(terminal)
        await terminal.size_set.wait()
        self._ncol = terminal.size.width
        self._nrow = terminal.size.height
        self._fd = self._open_terminal()
        self._p_out = os.fdopen(self._fd, "w+b", 0)
        self.task_group.start_soon(self._run)
        self.task_group.start_soon(self._receive)
        self.task_group.start_soon(self._send)
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

    async def _receive(self):
        try:
            while True:
                await wait_readable(self._p_out)
                self._data_or_disconnect = self._p_out.read(65536).decode()
                self._event.set()
        except Exception:
            self._data_or_disconnect = None
            self._event.set()

    async def _run(self):
        await self._send_queue.send(["setup", {}])
        while True:
            msg = await self._recv_queue.receive()
            if msg[0] == "stdin" and msg[1] is not None:
                self._p_out.write(msg[1].encode())
            elif msg[0] == "set_size":
                winsize = struct.pack("HH", msg[1], msg[2])
                fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)

    async def _send(self):
        while True:
            await self._event.wait()
            self._event = Event()
            if self._data_or_disconnect is None:
                await self._send_queue.send(["disconnect", 1])
            else:
                await self._send_queue.send(["stdout", self._data_or_disconnect])
