import os

from asphalt.core import Component, add_resource, request_resource

from txl.base import Header, Launcher, TerminalFactory, Terminals

if os.name == "nt":
    from .win_terminal import LocalTerminals
else:
    from .terminal import LocalTerminals


class LocalTerminalsComponent(Component):
    async def start(self) -> None:
        header = await request_resource(Header)
        terminal = await request_resource(TerminalFactory)
        launcher = await request_resource(Launcher)

        def terminals_factory():
            return LocalTerminals(header, terminal)

        launcher.register("terminal", terminals_factory)
        await add_resource(terminals_factory, types=Terminals)
