"""Shared application setup for CLI commands."""

from fps import get_root_module

from txl.app import AppModule


def create_app(settings, timeout, inline=False):
    config = {"type": AppModule, "config": {"cli": True, "inline": inline}}
    for setting in settings:
        if "=" not in setting:
            raise ValueError(f"No '=' while setting a module parameter: {setting}")
        key, value = setting.split("=", 1)
        node = config
        parts = key.split(".")
        for name in parts[:-1]:
            node = node.setdefault("modules", {}).setdefault(name, {})
        node.setdefault("config", {})[parts[-1]] = value
    module = get_root_module({"app": config})
    module._global_start_timeout = timeout
    return module
