"""Execute notebook cells through the configured kernel and contents services."""

from pathlib import PurePosixPath

import anyio
import rich_click as click

from txl.base import Contents, Kernels

from .app import create_app
from .kernel import create_notebook_kernel
from .show import show


async def execute_notebook(path, cell_id, settings, timeout, kernel_name=None, remote=False):
    if PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("Execution requires a notebook (.ipynb).")
    module = create_app(settings, timeout)
    deadline = anyio.current_time() + timeout
    async with module:
        with anyio.fail_after(max(0, deadline - anyio.current_time())):
            contents = await module.get(Contents)
            document = await contents.get(path, type="notebook")
            if cell_id is None:
                cells = [cell for cell in document.ycells if cell["cell_type"] == "code"]
            else:
                cell = next(
                    (cell for cell in document.ycells if cell.get("id") == cell_id), None
                )
                if cell is None:
                    raise ValueError(f"Cell ID not found: {cell_id}")
                if cell["cell_type"] != "code":
                    raise ValueError(f"Cell is not a code cell: {cell_id}")
                cells = [cell]
            if not cells:
                return []
            kernels = await module.get(Kernels)
            kernel = create_notebook_kernel(path, document, kernels, kernel_name, remote)
            try:
                for cell in cells:
                    await kernel.execute(cell)
                    errors = [
                        output for output in cell["outputs"].to_py()
                        if output["output_type"] == "error"
                    ]
                    if errors:
                        break
                document.dirty = True
                await contents.save(path, document)
                return errors
            finally:
                if not remote:
                    with anyio.CancelScope(shield=True):
                        await kernel.aclose()


@click.command()
@click.argument("path")
@click.option("--cell", "cell_id", help="Execute only the code cell with this ID.")
@click.option("--kernel", "kernel_name", help="Kernel name when starting a new kernel.")
@click.option(
    "--json", "as_json", is_flag=True, help="Print the notebook or selected cell as JSON."
)
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to load, execute and save, in seconds.")
@click.pass_context
def execute(ctx, path, cell_id, kernel_name, as_json, timeout):
    """Execute a notebook locally or using its session on a Jupyter server.

    Local execution reuses a detached kernel for this notebook.
    With --server, execution reuses the notebook's server session.
    Without --cell, run code cells in order, stopping at the first cell error.
    Cell errors are saved and produce a nonzero exit status.
    """
    remote = bool(ctx.parent.params["server"])
    options = ctx.obj
    try:
        errors = anyio.run(
            execute_notebook, path, cell_id, options["set_"], timeout, kernel_name, remote,
            backend=options["backend"],
        )
    except Exception as exc:
        while getattr(exc, "exceptions", None):
            exc = exc.exceptions[0]
        message = "Timed out executing notebook" if isinstance(exc, TimeoutError) else str(exc)
        raise click.ClickException(message) from exc
    ctx.invoke(
        show, path=path, cell_id=cell_id, as_json=as_json,
        show_cell_ids=False, timeout=timeout,
    )
    if errors:
        raise click.ClickException(f"{errors[0]['ename']}: {errors[0]['evalue']}")
