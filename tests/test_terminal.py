from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import anyio
import pytest
from anytext._xterm_parser import XTermParser
from txl_terminal.main import _Terminal


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        ("\r", "\r"),
        ("\x1b[13;1u", "\r"),
        ("\x1b[57414;1u", "\r"),
        ("\x1b[9;1u", "\t"),
        ("\x1b[127;1u", "\x7f"),
        ("\x1b[27;1u", "\x1b"),
        ("\x1b[99;5u", "\x03"),
        ("\x1b[D", "\x1b[D"),
        ("x", "x"),
    ],
)
def test_terminal_forwards_key_input(sequence, expected):
    async def check():
        async with anyio.create_task_group() as tasks:
            shell_input = AsyncMock()
            terminal = _Terminal(shell_input, None, SimpleNamespace(set_label=Mock()), tasks)
            event, = XTermParser().feed(sequence)

            await terminal.on_key(event)

            shell_input.send.assert_awaited_once_with(["stdin", expected])
            tasks.cancel_scope.cancel()

    anyio.run(check)
