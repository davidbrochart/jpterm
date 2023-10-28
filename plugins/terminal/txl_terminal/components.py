import asyncio
from functools import partial

import pyte
from asphalt.core import Component, Context
from rich.console import RenderableType
from rich.text import Text
from textual import events
from textual.widget import Widget

from txl.base import MainArea, Terminal, TerminalFactory

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


class TerminalMeta(type(Terminal), type(Widget)):
    pass


class _Terminal(Terminal, Widget, metaclass=TerminalMeta, can_focus=True):
    DEFAULT_CSS = """
    _Terminal {
        height: 1fr;
    }
    """

    def __init__(self, send_queue, recv_queue, main_area: MainArea):
        super().__init__()
        self._send_queue = send_queue
        self._recv_queue = recv_queue
        self._display = PyteDisplay([Text()])
        self.size_set = asyncio.Event()
        asyncio.create_task(self._recv())
        main_area.set_label("Terminal")

    def render(self) -> RenderableType:
        return self._display

    def on_resize(self, event: events.Resize):
        self._ncol = event.size.width
        self._nrow = event.size.height - 3  # FIXME
        self._screen = pyte.Screen(self._ncol, self._nrow)
        self._stream = pyte.Stream(self._screen)
        self.size_set.set()

    async def on_key(self, event: events.Key) -> None:
        char = CTRL_KEYS.get(event.key) or event.character
        await self._send_queue.put(["stdin", char])
        event.stop()

    async def _recv(self):
        await self.size_set.wait()
        while True:
            message = await self._recv_queue.get()
            cmd = message[0]
            if cmd == "setup":
                await self._send_queue.put(["set_size", self._nrow, self._ncol, 567, 573])
            elif cmd == "stdout":
                chars = message[1]
                self._stream.feed(chars)
                lines = []
                for i, line in enumerate(self._screen.display):
                    text = Text.from_ansi(line)
                    x = self._screen.cursor.x
                    if i == self._screen.cursor.y and x < len(text):
                        cursor = text[x]
                        cursor.stylize("reverse")
                        new_text = text[:x]
                        new_text.append(cursor)
                        new_text.append(text[x + 1 :])
                        text = new_text
                    lines.append(text)
                self._display = PyteDisplay(lines)
                self.refresh()


class TerminalComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        main_area = await ctx.request_resource(MainArea)
        ctx.add_resource(partial(_Terminal, main_area=main_area), types=TerminalFactory)
