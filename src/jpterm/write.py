"""Write text files and notebook cell sources through the contents service."""

from importlib.metadata import entry_points
from pathlib import PurePosixPath
from typing import Annotated

import anyio
from cyclopts import Parameter

from txl.base import Contents

from .app import create_app
from .command import CommandError, Timeout, operation_error, runtime


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
                    (
                        i
                        for i, cell in enumerate(document.source["cells"])
                        if cell.get("id") == cell_id
                    ),
                    None,
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


async def write(
    path: str,
    *,
    cell_id: Annotated[
        str | None, Parameter(name="--cell", help="Replace this notebook cell's source.")
    ] = None,
    source: Annotated[
        str | None, Parameter(help="Replacement text (an empty string clears it).")
    ] = None,
    from_stdin: Annotated[
        bool, Parameter(name="--stdin", help="Read replacement text from stdin.")
    ] = False,
    timeout: Timeout = 30.0,
):
    """Write a text file or replace a notebook cell's source.

    Provide exactly one of --source or --stdin. Changed code cells have their
    saved outputs and execution count cleared. This command does not execute cells.
    """
    if (source is not None) == from_stdin:
        raise CommandError("Provide exactly one of --source or --stdin.")
    state = runtime()
    try:
        if from_stdin:
            source = await state.read_stdin()
        await write_document(
            state.path(path), source, cell_id, state.settings, timeout, state.collaborative
        )
        state.notify(path)
    except Exception as error:
        raise operation_error(error, "writing document") from error
