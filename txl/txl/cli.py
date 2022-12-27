import click

from .app import run


def MAIN(set_):
    return set_


def set_main(main):
    global MAIN
    MAIN = main


@click.option(
    "--configfile",
    type=str,
    multiple=True,
    help="Read YAML configuration file",
)
@click.option(
    "--set",
    "set_",
    multiple=True,
    type=str,
    help="Set configuration",
)
def txl_main(
    # txl_main can be decorated with other Click options through MAIN
    # they are passed in kwargs
    **kwargs,
) -> None:
    kwargs = MAIN(kwargs)
    # MAIN may have changed our options, based on its own options
    kwargs["set_"].append("component.type=txl.app:AppComponent")
    run(kwargs)


def main():
    command = click.command(txl_main)
    command()


if __name__ == "__main__":
    main()
