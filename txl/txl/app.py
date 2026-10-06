import logging
from importlib.metadata import entry_points
from shutil import get_terminal_size

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
    def __init__(self, name: str, cli: bool = False, inline: bool = False):
        super().__init__(name)
        self.cli = cli
        self.inline = inline
        self.app_ready = anyio.Event()
        self.app_exited = anyio.Event()
        for name, module_class in modules.items():
            if name not in disabled:
                self.add_module(module_class, name)

    async def start(self) -> None:
        self.done()
        app = await self.get(App)
        self.app = app
        app.cli = self.cli
        active_app.set(app)
        async def ready(pilot):
            self.app_ready.set()

        await app.run_async(
            headless=self.cli,
            inline=self.inline,
            inline_no_clear=self.inline,
            size=tuple(get_terminal_size()) if self.cli else None,
            auto_pilot=ready,
        )
        self.app_exited.set()
        if not self.cli:
            self.exit_app()


def run(kwargs) -> None:
    main.callback("txl.app:AppModule", None, **kwargs)
