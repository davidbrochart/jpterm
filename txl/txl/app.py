from asphalt.core import CLIApplicationComponent, Context
from asphalt.core.cli import run as asphalt_run
from pluggy import PluginManager
from textual.app import App

from txl import hooks
from txl.hooks import HookType


def get_pluggin_manager(hook_type: HookType) -> PluginManager:
    pm = PluginManager(hook_type.value)
    pm.add_hookspecs(hooks)
    pm.load_setuptools_entrypoints(hook_type.value)
    return pm


def load_components():
    pm = get_pluggin_manager(HookType.COMPONENT)
    return pm.hook.component()


class AppComponent(CLIApplicationComponent):
    def __init__(self, components=None, disable=[], enable=[]):
        super().__init__(components)
        self.disable = disable
        self.enable = enable

    async def start(self, ctx: Context) -> None:
        for name, component, config in load_components():
            add_component = config.pop("enable", True)
            plugin = component.__module__.split(".", 1)[0]
            if plugin in self.disable and plugin in self.enable:
                raise RuntimeError(f"Plugin cannot be disabled and enabled: {plugin}")
            if plugin in self.disable:
                add_component = False
            elif plugin in self.enable:
                add_component = True
            if add_component:
                self.add_component(name, component, **config)
        await super().start(ctx)

    async def run(self, ctx: Context) -> None:
        app = ctx.require_resource(App, "app")
        await app._process_messages()


def run(kwargs) -> None:
    asphalt_run.callback(unsafe=False, loop=None, service=None, **kwargs)


if __name__ == "__main__":
    run()
