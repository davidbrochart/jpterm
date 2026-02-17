import functools
import os
import sys

import rich_click as click
from rich import print as rich_print

from txl.app import disabled
from txl.cli import set_main, txl_main


def jpterm_main(kwargs):
    logo = kwargs.pop("logo")
    if logo:
        rich_print("[orange1 on black]\u256d" + "\u2500" * 5 + "\u256e")
        rich_print("jpterm[r] ")
        rich_print("[orange1 on black]\u2570" + "\u2500" * 5 + "\u256f")
        sys.exit(0)
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    experimental = kwargs.pop("experimental")
    set_ = list(kwargs["set_"])
    if server:
        set_.append(f"remote_contents.url={server}")
        set_.append(f"remote_terminals.url={server}")
        set_.append(f"remote_kernels.url={server}")
        set_.append(f"remote_kernelspecs.url={server}")
        set_.append(f"remote_contents.collaborative={collaborative}")
        set_.append(f"notebook_editor.experimental={experimental}")
        disabled.extend(
            [
                "local_contents",
                "local_terminals",
                "local_kernels",
                "local_kernelspecs",
            ]
        )
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
    _ensure_unicode_streams()
    set_main(jpterm_main)
    decorators = [
        click.option("--logo", is_flag=True, default=False, help="Show the jpterm logo."),
        click.option("--server", default="", help="The URL to the Jupyter server."),
        click.option(
            "--backend",
            default="asyncio",
            help="The name of the event loop to use (asyncio or trio).",
        ),
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


@functools.cache
def _ensure_unicode_streams() -> None:
    # Before Python 3.15, this isn't always unicode
    if (
        sys.version_info < (3, 15)
        and "PYTHONIOENCODING" not in os.environ
        and "PYTHONUTF8" not in os.environ
    ):
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
