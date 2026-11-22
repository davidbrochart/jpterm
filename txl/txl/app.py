import logging
from collections.abc import Awaitable, Callable
from importlib.metadata import entry_points
from shutil import get_terminal_size

import anyio
from anytext import alias_textual
from anytext._context import active_app
from anytext.app import App
from anytext.pilot import Pilot
from fps import Module, get_root_module

logging.getLogger("httpx2").setLevel(logging.CRITICAL)
logging.getLogger("httpcore2").setLevel(logging.CRITICAL)

# Plugins may still import Textual. Alias it before loading their entry points.
alias_textual()

modules = {
    ep.name: ep.load() for ep in entry_points(group="txl.modules")
}

disabled = []


class AppModule(Module):
    def __init__(
        self,
        name: str,
        cli: bool = False,
        inline: bool = False,
        disabled_modules: list[str] | None = None,
        host_app=None,
        on_ready: Callable[[Pilot], Awaitable[None]] | None = None,
    ):
        super().__init__(name)
        self.cli = cli
        self.host_app = host_app
        self.inline = inline
        self.on_ready = on_ready
        self.app_ready = anyio.Event()
        self.app_exited = anyio.Event()
        excluded = disabled if disabled_modules is None else disabled_modules
        for name, module_class in modules.items():
            if name not in excluded:
                self.add_module(module_class, name)

    async def start(self) -> None:
        self.done()
        if self.host_app is not None:
            # The host owns its terminal driver and application lifetime.
            self.app = self.host_app
            self.put(self.app, App)
            active_app.set(self.app)
            self.app_ready.set()
            await anyio.sleep_forever()
            return
        app = await self.get(App)
        self.app = app
        app.cli = self.cli
        active_app.set(app)

        async def ready(pilot):
            self.app_ready.set()
            if self.on_ready is not None:
                await self.on_ready(pilot)

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
    """Configure and run the root module without invoking a CLI parser."""
    options = dict(kwargs)
    backend = options.pop("backend", "asyncio")
    settings = options.pop("set_", ())
    timeout = options.pop("timeout", None)
    stop_timeout = options.pop("stop_timeout", 1)
    if options:
        raise TypeError(f"Unsupported startup options: {', '.join(options)}")
    config = {"type": AppModule}
    for setting in settings:
        if "=" not in setting:
            raise ValueError(f"No '=' while setting a module parameter: {setting}")
        key, value = setting.split("=", 1)
        node = config
        path = key.split(".")
        for name in path[:-1]:
            node = node.setdefault("modules", {}).setdefault(name, {})
        node.setdefault("config", {})[path[-1]] = value
    module = get_root_module({"root_module": config})
    module._global_start_timeout = timeout
    module._stop_timeout = stop_timeout
    module.run(backend=backend)
