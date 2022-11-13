import click
from txl.cli import set_main, txl_main


def jpterm_main(kwargs):
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    set_ = list(kwargs["set_"])
    if server:
        set_.append("component.disable=[txl_local_contents]")
        set_.append("component.enable=[txl_remote_contents]")
        set_.append(f"component.components.contents.url={server}")
        set_.append(f"component.components.contents.collaborative={collaborative}")
    else:
        set_.append("component.disable=[txl_remote_contents]")
        set_.append("component.enable=[txl_local_contents]")
    kwargs["set_"] = set_
    return kwargs


def main():
    set_main(jpterm_main)
    decorators = [
        click.option("--server", default="", help="The URL to the Jupyter server."),
        click.option("--collaborative/--no-collaborative", default=False, help="Collaborative mode (with a server)."),
    ]
    _main = txl_main
    for decorator in decorators[::-1]:
        _main = decorator(_main)
    command = click.command(_main)
    command()