import functools
import os
import sys
from inspect import isawaitable
from typing import Annotated, Literal

import anyio
from cyclopts import App, CycloptsError, Parameter
from rich.console import Console
from rich.text import Text

from txl.app import disabled, modules

from .command import CommandError, Runtime, current_runtime, operation_error, runtime
from .execute import execute
from .kernel import kernel
from .show import show
from .write import write


def jpterm_main(kwargs):
    server = kwargs.pop("server")
    collaborative = kwargs.pop("collaborative")
    experimental = kwargs.pop("experimental")
    set_ = list(kwargs["set_"])
    backend_modules = {name for name in modules if name.startswith(("local_", "remote_"))}
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


app = App(name="jpterm", help="Jupyter in the terminal.", version_flags=())
app.command(show)
app.command(write)
app.command(execute)
app.command(kernel)


@app.command
async def logo():
    """Show the jpterm logo."""
    await runtime().emit(
        Text.from_markup(
            "[orange1 on black]╭─────╮[/]\njpterm[r] [/r]\n[orange1 on black]╰─────╯[/]"
        )
    )


@app.meta.default
async def dispatch(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    server: Annotated[str, Parameter(help="The URL to the Jupyter server.")] = "",
    backend: Annotated[
        Literal["asyncio", "trio"], Parameter(help="Standalone event loop backend.")
    ] = "asyncio",
    collaborative: Annotated[bool, Parameter(help="Collaborative mode (with a server).")] = False,
    experimental: Annotated[bool, Parameter(help="Experimental mode (with Jupyverse).")] = False,
    set_: Annotated[list[str], Parameter(name="--set", help="Set configuration.")] = (),
    ctx: Annotated[object, Parameter(parse=False)] = None,
    stdin: Annotated[object, Parameter(parse=False)] = None,
    stdout: Annotated[object, Parameter(parse=False)] = None,
):
    if collaborative and not server:
        raise CommandError("--collaborative requires --server for CLI commands.")
    options = jpterm_main(
        dict(
            server=server,
            collaborative=collaborative,
            experimental=experimental,
            backend=backend,
            set_=set_,
        )
    )
    state = Runtime(options["set_"], list(disabled), server, collaborative, ctx, stdin, stdout)
    token = current_runtime.set(state)
    try:
        if not tokens:
            await state.open_view()
            return
        callback, bound, ignored = app.parse_args(
            tokens, print_error=False, exit_on_error=False, help_on_error=False
        )
        if ignored:
            raise CommandError(f"Unsupported command dependencies: {', '.join(ignored)}")
        result = callback(*bound.args, **bound.kwargs)
        if isawaitable(result):
            await result
    finally:
        current_runtime.reset(token)


def main():
    _ensure_unicode_streams()
    try:
        callback, bound, _ = app.meta.parse_args(
            sys.argv[1:], print_error=False, exit_on_error=False, help_on_error=False
        )
        bound.apply_defaults()
        if callback is dispatch and not bound.arguments.get("tokens"):
            # FPS owns the TUI lifecycle and starts its event loop itself.
            from txl.app import run

            options = {
                name: value
                for name, value in bound.arguments.items()
                if name not in {"tokens", "ctx", "stdin", "stdout"}
            }
            run(jpterm_main(options))
            return

        async def invoke():
            result = callback(*bound.args, **bound.kwargs)
            if isawaitable(result):
                await result

        anyio.run(invoke, backend=bound.arguments.get("backend", "asyncio"))
    except CycloptsError as error:
        Console(stderr=True).print(f"Error: {error}", markup=False)
        raise SystemExit(2) from error
    except Exception as error:
        message = operation_error(error, "running command")
        Console(stderr=True).print(f"Error: {message}", markup=False)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        raise SystemExit(130) from None


@functools.cache
def _ensure_unicode_streams() -> None:
    # Before Python 3.15, this isn't always unicode.
    if (
        sys.version_info < (3, 15)
        and "PYTHONIOENCODING" not in os.environ
        and "PYTHONUTF8" not in os.environ
    ):
        if sys.stdout.encoding != "utf-8" and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding != "utf-8" and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
