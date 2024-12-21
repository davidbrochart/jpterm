import os

from anyio import create_task_group, sleep
from fps import Module

from txl.base import Header, Launcher, TerminalFactory, Terminals

if os.name == "nt":
    from .win_terminal import LocalTerminals
else:
    from .terminal import LocalTerminals


class LocalTerminalsModule(Module):
    async def start(self) -> None:
        header = await self.get(Header)
        terminal = await self.get(TerminalFactory)
        launcher = await self.get(Launcher)

        async with create_task_group() as self.tg:
            def terminals_factory():
                return LocalTerminals(self.tg, header, terminal)

            launcher.register("terminal", terminals_factory)
            self.put(terminals_factory, Terminals)
            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        self.tg.cancel_scope.cancel()
