import logging
from importlib.metadata import entry_points

import anyio
from fps import Module
from fps.cli._cli import main
from textual._context import active_app
from textual.app import App

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)

modules = {
    ep.name: ep.load() for ep in entry_points(group="txl.modules")
}

disabled = []


class AppModule(Module):
    def __init__(self, name: str):
        super().__init__(name)
        self.app_exited = anyio.Event()
        for name, module_class in modules.items():
            if name not in disabled:
                self.add_module(module_class, name)

    async def start(self) -> None:
        self.done()
        app = await self.get(App)
        active_app.set(app)
        await app.run_async()
        self.app_exited.set()


def run(kwargs) -> None:
    main.callback("txl.app:AppModule", None, **kwargs)
