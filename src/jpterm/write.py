"""Write text files and notebook cell sources through the contents service."""

from importlib.metadata import entry_points
from pathlib import PurePosixPath

import anyio
import rich_click as click

from txl.base import Contents

from .app import create_app


async def write_document(path, source, cell_id, settings, timeout, collaborative=False):
    notebook = PurePosixPath(path).suffix == ".ipynb"
    if notebook and cell_id is None:
        raise ValueError("Writing a notebook requires --cell CELL_ID.")
    if not notebook and cell_id is not None:
        raise ValueError("--cell requires a notebook (.ipynb).")
    module = create_app(settings, timeout)
    with anyio.fail_after(timeout):
        async with module:
            contents = await module.get(Contents)
            if notebook:
                document = await contents.get(path, type="notebook")
                index = next(
                    (i for i, cell in enumerate(document.source["cells"])
                     if cell.get("id") == cell_id), None
                )
                if index is None:
                    raise ValueError(f"Cell ID not found: {cell_id}")
                cell = document.ycells[index]
                if str(cell["source"]) == source:
                    return
                with document.ydoc.transaction():
                    document.set_cell(index, source=source)
                    if cell["cell_type"] == "code":
                        cell["outputs"].clear()
                        cell["execution_count"] = None
                    document.dirty = True
            else:
                try:
                    document = await contents.get(path, type="file", format="text")
                except FileNotFoundError:
                    if collaborative:
                        raise
                    factory = next(iter(entry_points(group="jupyter_ydoc", name="file"))).load()
                    document = factory()
                if collaborative and document.source == source:
                    return
                with document.ydoc.transaction():
                    document.source = source
                    document.dirty = True
            if not collaborative:
                await contents.save(path, document)


@click.command()
@click.argument("path")
@click.option("--cell", "cell_id", help="Replace the source of the notebook cell with this ID.")
@click.option("--source", help="Replacement text (use an empty string to clear it).")
@click.option("--stdin", "from_stdin", is_flag=True, help="Read replacement text from stdin.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to load and save, in seconds.")
@click.pass_context
def write(ctx, path, cell_id, source, from_stdin, timeout):
    """Write a text file or replace a notebook cell's source.

    Provide exactly one of --source or --stdin. Changed code cells have their saved
    outputs and execution count cleared. This command does not execute cells.
    """
    if (source is not None) == from_stdin:
        raise click.UsageError("Provide exactly one of --source or --stdin.")
    if from_stdin:
        source = click.get_text_stream("stdin").read()
    options = ctx.obj
    try:
        anyio.run(
            write_document, path, source, cell_id, options["set_"], timeout,
            ctx.parent.params["collaborative"],
            backend=options["backend"],
        )
    except Exception as exc:
        while getattr(exc, "exceptions", None):
            exc = exc.exceptions[0]
        message = "Timed out writing document" if isinstance(exc, TimeoutError) else str(exc)
        raise click.ClickException(message) from exc
