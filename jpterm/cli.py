import click
from txl.cli import set_main, txl_main


def jpterm_main(**kwargs):
    server = kwargs["server"]
    if server:
        kwargs["disable"] = "txl_local_contents"
        kwargs["enable"] = "txl_remote_contents"
    return kwargs


def main():
    set_main(jpterm_main)
    _main = click.option("--server", default="", help="The URL to the Jupyter server.")(txl_main)
    command = click.command(_main)
    command()
