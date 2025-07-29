import os
from functools import partial

from anyio import create_task_group, to_thread
from anyioutils import Event, Queue
from textual.widget import Widget
from textual.widgets._header import HeaderTitle
from winpty import PTY

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
        self._process = self._open_terminal()
        self.task_group.start_soon(self._run)
        self.header.query_one(HeaderTitle).text = "Terminal"

    def _open_terminal(self):
        command = "C:\\Windows\\System32\\cmd.exe"
        env = "\0".join([f"{k}={v}" for k, v in os.environ.items()]) + "\0"
        process = PTY(self._ncol, self._nrow)
        process.spawn(command, env=env)
        return process

    async def _run(self):
        await self._send_queue.put(["setup", {}])

        async with create_task_group() as tg:
            tg.start_soon(self._send)
            tg.start_soon(self._recv)

    async def _send(self):
        while True:
            try:
                data = await to_thread.run_sync(partial(self._process.read, blocking=True))
            except Exception:
                await self._send_queue.put(["disconnect", 1])
                return
            else:
                await self._send_queue.put(["stdout", data])

    async def _recv(self):
        while True:
            try:
                msg = await self._recv_queue.get()
            except Exception:
                return
            if msg[0] == "stdin":
                self._process.write(msg[1])
            elif msg[0] == "set_size":
                self._process.set_size(msg[2], msg[1])
