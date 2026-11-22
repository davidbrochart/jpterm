"""Runtime services shared by the standalone CLI and embedded command tree."""

import json
import math
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Annotated

import anyio
from cyclopts import Parameter
from rich.console import Console
from rich.protocol import is_renderable


class CommandError(Exception):
    """An operation failed; display its message without a Python traceback."""


def operation_error(error, action):
    while isinstance(error, ExceptionGroup):
        error = error.exceptions[0]
    if isinstance(error, TimeoutError):
        return CommandError(f"Timed out {action}")
    return CommandError(str(error) or type(error).__name__)


@dataclass
class Runtime:
    settings: list[str]
    disabled_modules: list[str]
    server: str = ""
    collaborative: bool = False
    ctx: object = None
    stdin: object = None
    stdout: object = None
    console: Console = field(default_factory=Console)

    @property
    def is_terminal(self):
        # The standalone CLI renders documents even when its output is captured.
        return self.stdout is None or self.stdout.is_terminal

    @property
    def width(self):
        return self.console.width if self.ctx is None else self.ctx.output_width

    def path(self, path):
        if self.ctx is None:
            return path
        if self.server:
            return self.ctx.resolve(path).lstrip("/")
        if not hasattr(self.ctx.fs, "_path"):
            raise CommandError("Local jpterm commands require a local filesystem")
        return str(self.ctx.fs._path(self.ctx.resolve(path)))

    async def open_view(self):
        if self.ctx is None or self.stdout is None or not self.is_terminal:
            raise CommandError("The interactive UI requires an Anytext host with terminal output")
        from .view import open_view

        try:
            await self.ctx.open_view(lambda host_app: open_view(host_app, self))
        except Exception as error:
            raise operation_error(error, "opening interface") from error

    async def emit(self, value):
        if self.stdout is not None:
            await self.stdout.send(value)
        elif not isinstance(value, str) and is_renderable(value):
            self.console.print(value)
        else:
            print(
                value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
            )

    async def read_stdin(self):
        if self.stdin is None:
            return await anyio.to_thread.run_sync(sys.stdin.read)
        values = []
        async for value in self.stdin:
            if not isinstance(value, str):
                raise CommandError("--stdin requires text input")
            values.append(value)
        return "\n".join(values)

    def notify(self, path):
        if self.ctx is not None and not self.server:
            self.ctx.fs._notify(self.ctx.resolve(path), reset=True)


current_runtime = ContextVar("jpterm_command_runtime", default=None)


def runtime():
    result = current_runtime.get()
    if result is None:
        raise RuntimeError("The command must run through jpterm's CLI dispatcher")
    return result


def validate_timeout(type_, value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be finite and positive")


Timeout = Annotated[
    float, Parameter(validator=validate_timeout, help="Maximum operation duration in seconds.")
]
