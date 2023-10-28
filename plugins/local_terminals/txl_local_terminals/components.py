import os

from asphalt.core import Component, Context

from txl.base import Header, Launcher, TerminalFactory, Terminals

if os.name == "nt":
    from .win_terminal import LocalTerminals
else:
    from .terminal import LocalTerminals


class LocalTerminalsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header)
        terminal = await ctx.request_resource(TerminalFactory)
        launcher = await ctx.request_resource(Launcher)

        def terminals_factory():
            return LocalTerminals(header, terminal)

        launcher.register("terminal", terminals_factory)
        ctx.add_resource(terminals_factory, types=Terminals)
