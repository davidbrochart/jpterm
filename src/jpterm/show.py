"""Render documents off-screen and print their full-height layout once."""

import json
from pathlib import PurePosixPath
from typing import Annotated

import anyio
from cyclopts import Parameter

from txl.base import Contents, Editors

from .app import create_app
from .command import Timeout, operation_error, runtime


async def load_document(
    path,
    settings,
    timeout,
    render=False,
    cell_id=None,
    show_cell_ids=False,
    *,
    return_renderable=False,
    width=None,
):
    """Load source, print an editor layout, or return that layout to a host UI.

    With render=True and return_renderable=True, rendering stays headless and
    returns a frozen Rich renderable without writing to the process terminal.
    """
    if return_renderable and not render:
        raise ValueError("return_renderable requires render=True")
    if width is not None and width < 1:
        raise ValueError("width must be positive")
    rendered = None
    if cell_id is not None and PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("--cell requires a notebook (.ipynb).")
    if show_cell_ids and PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("--show-cell-ids requires a notebook (.ipynb).")

    async def render_document(pilot):
        nonlocal rendered
        app = pilot.app
        if width is not None:
            await pilot.resize_terminal(width, app.size.height)
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

        # Drain child-widget messages before measuring their final layout.
        await pilot.pause()
        while True:
            height = max(1, editor.virtual_size.height + editor.styles.gutter.height)
            if app.size.height == app.screen.size.height == height:
                break
            await pilot.resize_terminal(app.size.width, height)
            await pilot.pause()
        # Freeze the finished layout before the app shuts down.
        rendered = app.screen._compositor.__rich__()
        app.exit(message=None if return_renderable else rendered)

    # Render inside Anytext’s task context, after the editor plugins have registered.
    modules_ready = anyio.Event()
    render_error = None

    async def on_ready(pilot):
        nonlocal render_error
        await modules_ready.wait()
        try:
            await render_document(pilot)
        except Exception as exc:
            render_error = exc
            pilot.app.exit()

    module = create_app(
        settings,
        timeout,
        inline=render and not return_renderable,
        on_ready=on_ready if render else None,
    )
    deadline = anyio.current_time() + timeout
    async with module:
        with anyio.fail_after(max(0, deadline - anyio.current_time())):
            if render:
                modules_ready.set()
                await module.app_exited.wait()
                if render_error is not None:
                    raise render_error
                return rendered if return_renderable else None
            contents = await module.get(Contents)
            kind = "notebook" if PurePosixPath(path).suffix == ".ipynb" else "file"
            document = await contents.get(path, type=kind)
            source = document.source
            if cell_id is not None:
                source = next((cell for cell in source["cells"] if cell.get("id") == cell_id), None)
                if source is None:
                    raise ValueError(f"Cell ID not found: {cell_id}")
        return source


async def show(
    path: str,
    *,
    as_json: Annotated[
        bool, Parameter(name="--json", help="Print the document source as JSON.")
    ] = False,
    cell_id: Annotated[
        str | None, Parameter(name="--cell", help="Show only this notebook cell.")
    ] = None,
    show_cell_ids: Annotated[bool, Parameter(help="Display cell IDs after their prompts.")] = False,
    timeout: Timeout = 30.0,
):
    """Show document PATH inline using its registered editor, without executing cells."""
    state = runtime()
    try:
        document = await load_document(
            state.path(path),
            state.settings,
            timeout,
            state.is_terminal and not as_json,
            cell_id,
            show_cell_ids,
            return_renderable=state.is_terminal and not as_json,
            width=state.width,
        )
        if as_json:
            await state.emit(json.dumps(document, indent=2, ensure_ascii=False))
        elif not state.is_terminal and isinstance(document, str):
            for line in document.splitlines():
                await state.emit(line)
        else:
            await state.emit(document)
    except Exception as error:
        raise operation_error(error, "loading document") from error
