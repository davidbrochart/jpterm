import pkg_resources
from asphalt.core import CLIApplicationComponent, Context
from asphalt.core.cli import run as asphalt_run
from textual.app import App

components = {
    ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="txl.components")
}

disabled = []


class AppComponent(CLIApplicationComponent):
    def __init__(self, components=None):
        super().__init__(components)

    async def start(self, ctx: Context) -> None:
        for name, component in components.items():
            if name not in disabled:
                self.add_component(name, component)
        await super().start(ctx)

    async def run(self, ctx: Context) -> None:
        app = ctx.require_resource(App)
        await app.run_async()


def run(kwargs) -> None:
    asphalt_run.callback(unsafe=False, loop=None, service=None, **kwargs)


if __name__ == "__main__":
    run()
