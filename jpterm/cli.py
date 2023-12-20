import sys

import rich_click as click
from rich import print as rich_print

from txl.app import disabled
from txl.cli import set_main, txl_main


def jpterm_main(kwargs):
    logo = kwargs.pop("logo")
    if logo:
        rich_print("[orange1 on black]\u256d\u2500\u2500\u2500\u2500\u2500\u256e")
        rich_print("[white on black]jpterm\u2588")
        rich_print("[orange1 on black]\u2570\u2500\u2500\u2500\u2500\u2500\u256f")
        rich_print("[bright_black on black]  \u25cf \u25cf  ")
        sys.exit(1)
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    experimental = kwargs.pop("experimental")
    set_ = list(kwargs["set_"])
    set_.append("logging.version=1")  # disable logging
    if server:
        set_.append(f"component.components.remote_contents.url={server}")
        set_.append(f"component.components.remote_terminals.url={server}")
        set_.append(f"component.components.remote_kernels.url={server}")
        set_.append(f"component.components.remote_kernelspecs.url={server}")
        set_.append(f"component.components.remote_contents.collaborative={collaborative}")
        set_.append(f"component.components.notebook_editor.experimental={experimental}")
        disabled.extend(["local_contents", "local_terminals", "local_kernels", "local_kernelspecs"])
    else:
        disabled.extend(
            [
                "remote_contents",
                "remote_terminals",
                "remote_kernels",
                "remote_kernelspecs",
            ]
        )
    kwargs["set_"] = set_
    return kwargs


def main():
    set_main(jpterm_main)
    decorators = [
        click.option("--logo", is_flag=True, default=False, help="Show the jpterm logo."),
        click.option("--server", default="", help="The URL to the Jupyter server."),
        click.option(
            "--collaborative/--no-collaborative",
            default=False,
            help="Collaborative mode (with a server).",
        ),
        click.option(
            "--experimental/--no-experimental",
            default=False,
            help="Experimental mode (with Jupyverse).",
        ),
    ]
    _main = txl_main
    for decorator in decorators[::-1]:
        _main = decorator(_main)
    command = click.command()(_main)
    command()
