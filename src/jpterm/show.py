"""Render documents off-screen and print their full-height layout once."""

import json
from pathlib import PurePosixPath

import anyio
import rich_click as click
from fps import get_root_module
from textual import events
from textual.geometry import Size

from txl.app import AppModule
from txl.base import Contents, Editors


async def load_document(path, settings, timeout, inline=False):
    config = {"type": AppModule, "config": {"cli": True, "inline": inline}}
    for setting in settings:
        if "=" not in setting:
            raise ValueError(f"No '=' while setting a module parameter: {setting}")
        key, value = setting.split("=", 1)
        node = config
        parts = key.split(".")
        for name in parts[:-1]:
            node = node.setdefault("modules", {}).setdefault(name, {})
        node.setdefault("config", {})[parts[-1]] = value
    module = get_root_module({"app": config})
    module._global_start_timeout = timeout
    with anyio.fail_after(timeout):
        async with module:
            if inline:
                await module.app_ready.wait()
                app = module.app
                editors = await module.get(Editors)
                editor = editors.create_editor(path)
                editor.read_only = True
                editor.styles.height = "auto"
                editor.styles.overflow_y = "hidden"
                editor.styles.scrollbar_size_vertical = 0
                app.screen.styles.height = "auto"
                app.screen.styles.border = ("none", "transparent")
                app.screen.styles.padding = 0
                app.screen.styles.scrollbar_size_vertical = 0
                await app.screen.mount(editor)
                await editor.open(path)

                def show_full_height():
                    height = max(1, editor.virtual_size.height + editor.styles.gutter.height)
                    size = Size(app.size.width, height)
                    if app.size == size:
                        # Freeze the finished layout before the app shuts down.
                        app.exit(message=app.screen._compositor.__rich__())
                        return
                    app.post_message(events.Resize(size, size))
                    app.screen.post_message(events.Resize(size, size))
                    app.call_after_refresh(lambda: app.call_after_refresh(show_full_height))

                app.call_after_refresh(show_full_height)
                await module.app_exited.wait()
                return None
            else:
                contents = await module.get(Contents)
                kind = "notebook" if PurePosixPath(path).suffix == ".ipynb" else "file"
                document = await contents.get(path, type=kind)
                source = document.source
        return source


@click.command()
@click.argument("path")
@click.option("--json", "as_json", is_flag=True, help="Print the document source as JSON.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to load and synchronize, in seconds.")
@click.pass_context
def show(ctx, path, as_json, timeout):
    """Show document PATH inline using its registered editor.

    Display the full document and return immediately. This command does not execute cells.
    Use --json for structured output.
    """
    options = ctx.obj
    if options["collaborative"] and not options["server"]:
        raise click.UsageError("--collaborative requires --server for show.")
    try:
        from .cli import jpterm_main

        configured = jpterm_main(dict(options))
        source = anyio.run(
            load_document, path, configured["set_"], timeout, not as_json,
            backend=options["backend"],
        )
        if as_json:
            click.echo(json.dumps(source, indent=2, ensure_ascii=False))
    except Exception as exc:
        # AnyIO task groups may wrap the original loading error.
        while getattr(exc, "exceptions", None):
            exc = exc.exceptions[0]
        message = "Timed out loading document" if isinstance(exc, TimeoutError) else str(exc)
        raise click.ClickException(message) from exc
