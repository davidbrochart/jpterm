"""Shared application setup for CLI commands."""

from fps import get_root_module

from txl.app import AppModule


def create_app(settings, timeout, inline=False, on_ready=None, host_app=None):
    from .command import current_runtime

    config = {"type": AppModule, "config": {"cli": True, "inline": inline}}
    if host_app is not None:
        config["config"].update(cli=False, host_app=host_app)
        config["modules"] = {"jpterm": {"config": {"embedded": True}}}
    state = current_runtime.get()
    if state is not None:
        config["config"]["disabled_modules"] = state.disabled_modules
    for setting in settings:
        if "=" not in setting:
            raise ValueError(f"No '=' while setting a module parameter: {setting}")
        key, value = setting.split("=", 1)
        node = config
        parts = key.split(".")
        for name in parts[:-1]:
            node = node.setdefault("modules", {}).setdefault(name, {})
        node.setdefault("config", {})[parts[-1]] = value
    if on_ready is not None:
        config["config"]["on_ready"] = on_ready
    module = get_root_module({"app": config})
    module._global_start_timeout = timeout
    return module
