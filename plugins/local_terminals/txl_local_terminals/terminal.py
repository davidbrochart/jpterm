import fcntl
import os
import pty
import shlex
import struct
import termios

from anyio import wait_readable
from anyioutils import Event, Queue
from textual.widget import Widget
from textual.widgets._header import HeaderTitle

from txl.base import Header, TerminalFactory, Terminals


class TerminalsMeta(type(Terminals), type(Widget)):
    pass


class LocalTerminals(Terminals, Widget, metaclass=TerminalsMeta):
    def __init__(self, task_group, header: Header, terminal: TerminalFactory):
        self.task_group = task_group
        self.header = header
        self.terminal = terminal
        self._send_queue = Queue()
        self._recv_queue = Queue()
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
