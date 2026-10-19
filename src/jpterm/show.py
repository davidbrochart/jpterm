"""Render documents off-screen and print their full-height layout once."""

import json
from pathlib import PurePosixPath

import anyio
import rich_click as click
from textual import events
from textual.geometry import Size

from txl.base import Contents, Editors

from .app import create_app


async def load_document(path, settings, timeout, render=False, cell_id=None, show_cell_ids=False):
    if cell_id is not None and PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("--cell requires a notebook (.ipynb).")
    if show_cell_ids and PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("--show-cell-ids requires a notebook (.ipynb).")
    module = create_app(settings, timeout, inline=render)
    with anyio.fail_after(timeout):
        async with module:
            if render:
                await module.app_ready.wait()
                app = module.app
                editors = await module.get(Editors)
                editor = editors.create_editor(path)
                editor.styles.height = "auto"
                editor.styles.overflow_y = "hidden"
                editor.styles.scrollbar_size_vertical = 0
                app.screen.styles.height = "auto"
                app.screen.styles.border = ("none", "transparent")
                app.screen.styles.padding = 0
                app.screen.styles.scrollbar_size_vertical = 0
                await app.screen.mount(editor)
                if cell_id is None and not show_cell_ids:
                    await editor.open(path)
                else:
                    await editor.open(path, cell_id=cell_id, show_cell_ids=show_cell_ids)

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
                if cell_id is not None:
                    source = next(
                        (cell for cell in source["cells"] if cell.get("id") == cell_id), None
                    )
                    if source is None:
                        raise ValueError(f"Cell ID not found: {cell_id}")
        return source


@click.command()
@click.argument("path")
@click.option("--json", "as_json", is_flag=True, help="Print the document source as JSON.")
@click.option("--cell", "cell_id", help="Show only the notebook cell with this ID.")
@click.option("--show-cell-ids", is_flag=True, help="Display cell IDs after their prompts.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to load and synchronize, in seconds.")
@click.pass_context
def show(ctx, path, as_json, cell_id, show_cell_ids, timeout):
    """Show document PATH inline using its registered editor.

    Display the full document and return immediately. This command does not execute cells.
    Use --json for structured output.
    """
    options = ctx.obj
    try:
        source = anyio.run(
            load_document, path, options["set_"], timeout, not as_json, cell_id, show_cell_ids,
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
