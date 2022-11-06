from typing import List, Optional

import typer
from asphalt.core.cli import run as asphalt_run

from .app import run


def main(
    configfiles: Optional[List[str]] = typer.Argument(None),
    disable: str = typer.Option("", help="Comma-separated list of plugins to disable"),
    enable: str = typer.Option("", help="Comma-separated list of plugins to enable"),
) -> None:
    disabled_plugins = [plugin.strip() for plugin in disable.split(",")]
    enabled_plugins = [plugin.strip() for plugin in enable.split(",")]
    if configfiles:
        asphalt_run(configfiles)
    else:
        run(disabled_plugins, enabled_plugins)


def run_main():
    typer.run(main)


if __name__ == "__main__":
    run_main()
