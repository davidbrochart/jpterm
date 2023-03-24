import rich_click as click

from txl.app import disabled
from txl.cli import set_main, txl_main


def jpterm_main(kwargs):
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    set_ = list(kwargs["set_"])
    if server:
        set_.append(f"component.components.remote_contents.url={server}")
        set_.append(f"component.components.remote_terminals.url={server}")
        set_.append(f"component.components.remote_kernels.url={server}")
        set_.append(
            f"component.components.remote_contents.collaborative={collaborative}"
        )
        disabled.extend(["local_contents", "local_terminals", "local_kernels"])
    else:
        disabled.extend(["remote_contents", "remote_terminals", "remote_kernels"])
    kwargs["set_"] = set_
    return kwargs


def main():
    set_main(jpterm_main)
    decorators = [
        click.option("--server", default="", help="The URL to the Jupyter server."),
        click.option(
            "--collaborative/--no-collaborative",
            default=False,
            help="Collaborative mode (with a server).",
        ),
    ]
    _main = txl_main
    for decorator in decorators[::-1]:
        _main = decorator(_main)
    command = click.command(_main)
    command()
