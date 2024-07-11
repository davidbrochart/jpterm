from importlib.metadata import entry_points

from asphalt.core import CLIApplicationComponent, require_resource
from asphalt.core._cli import run as asphalt_run
from textual.app import App

components = {
    ep.name: ep.load() for ep in entry_points(group="txl.components")
}

disabled = []


class AppComponent(CLIApplicationComponent):
    def __init__(self, components=None):
        super().__init__(components)

    async def start(self) -> None:
        for name, component in components.items():
            if name not in disabled:
                self.add_component(name, component)
        await super().start()

    async def run(self) -> None:
        app = require_resource(App)
        await app.run_async()


def run(kwargs) -> None:
    asphalt_run.callback(service=None, **kwargs)


if __name__ == "__main__":
    run()
