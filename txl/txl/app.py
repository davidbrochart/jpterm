from typing import List

from asphalt.core import CLIApplicationComponent, Context, run_application
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

    def __init__(self, disabled_plugins, enabled_plugins):
        super().__init__()
        self.disabled_plugins = disabled_plugins
        self.enabled_plugins = enabled_plugins

    async def start(self, ctx: Context) -> None:
        for name, component, config in load_components():
            add_component = config.pop("enabled", True)
            plugin = component.__module__.split(".", 1)[0]
            if plugin in self.disabled_plugins and plugin in self.enabled_plugins:
                raise RuntimeError(f"plugin cannot be disabled and enabled ({plugin})")
            if plugin in self.disabled_plugins:
                add_component = False
            elif plugin in self.enabled_plugins:
                add_component = True
            if add_component:
                self.add_component(name, component, **config)
        await super().start(ctx)

    async def run(self, ctx: Context) -> None:
        app = ctx.require_resource(App, "app")
        await app._process_messages()


def run(disabled_plugins: List[str], enabled_plugins: List[str]):
    run_application(AppComponent(disabled_plugins, enabled_plugins))


if __name__ == "__main__":
    run()
