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

    async def start(self, ctx: Context) -> None:
        for name, component, config in load_components():
            self.add_component(name, component, **config)
        await super().start(ctx)

    async def run(self, ctx: Context) -> None:
        app = ctx.require_resource(App, "app")
        await app._process_messages()


def run():
    run_application(AppComponent())


if __name__ == "__main__":
    run()
