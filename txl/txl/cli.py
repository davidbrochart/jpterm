import click
from asphalt.core.cli import run as asphalt_run

from .app import run


def MAIN(**kwargs):
    return kwargs


def set_main(main):
    global MAIN
    MAIN = main


@click.option("--configfiles", default="", help="Comma-separated list of configuration files")
@click.option("--disable", default="", help="Comma-separated list of plugins to disable")
@click.option("--enable", default="", help="Comma-separated list of plugins to enable")
def txl_main(
    **kwargs,
) -> None:
    kwargs = MAIN(**kwargs)
    disabled_plugins = [plugin.strip() for plugin in kwargs["disable"].split(",")]
    enabled_plugins = [plugin.strip() for plugin in kwargs["enable"].split(",")]
    configfiles = kwargs["configfiles"]
    if configfiles:
        asphalt_run(configfiles)
    else:
        run(disabled_plugins, enabled_plugins)

def main():
    command = click.command(txl_main)
    command()


if __name__ == "__main__":
    main()
