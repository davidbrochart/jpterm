import functools
import os
import sys

import rich_click as click
from rich import print as rich_print

from txl.app import disabled, modules
from txl.cli import set_main, txl_main

from .show import show


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
    backend_modules = {
        name for name in modules if name.startswith(("local_", "remote_"))
    }
    disabled[:] = [name for name in disabled if name not in backend_modules]
    disabled.extend(
        name for name in backend_modules if name.startswith("local_" if server else "remote_")
    )
    if server:
        set_.append(f"remote_contents.url={server}")
        set_.append(f"remote_terminals.url={server}")
        set_.append(f"remote_kernels.url={server}")
        set_.append(f"remote_kernelspecs.url={server}")
        set_.append(f"remote_contents.collaborative={collaborative}")
        set_.append(f"notebook_editor.experimental={experimental}")
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
    @functools.wraps(txl_main)
    def _main(**kwargs):
        return txl_main(**kwargs)

    _main.__click_params__ = list(getattr(txl_main, "__click_params__", []))
    for decorator in decorators[::-1]:
        _main = decorator(_main)
    @click.group(invoke_without_command=True)
    @click.pass_context
    def command(ctx, **kwargs):
        if ctx.invoked_subcommand is None:
            _main(**kwargs)
        else:
            if kwargs["collaborative"] and not kwargs["server"]:
                raise click.UsageError("--collaborative requires --server for CLI commands.")
            ctx.obj = jpterm_main(kwargs)

    # Keep the existing TUI options on the root command.
    command.params.extend(click.command()(_main).params)
    command.add_command(show)
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
