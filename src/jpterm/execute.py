"""Execute notebook cells through the configured kernel and contents services."""

from pathlib import PurePosixPath
from typing import Annotated

import anyio
from cyclopts import Parameter

from txl.base import Contents, Kernels

from .app import create_app
from .command import CommandError, Timeout, operation_error, runtime
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
                cell = next((cell for cell in document.ycells if cell.get("id") == cell_id), None)
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
                        output
                        for output in cell["outputs"].to_py()
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


async def execute(
    path: str,
    *,
    cell_id: Annotated[
        str | None, Parameter(name="--cell", help="Execute only this code cell.")
    ] = None,
    kernel_name: Annotated[
        str | None, Parameter(name="--kernel", help="Kernel name when starting a new kernel.")
    ] = None,
    as_json: Annotated[
        bool, Parameter(name="--json", help="Print the updated notebook or cell as JSON.")
    ] = False,
    timeout: Timeout = 30.0,
):
    """Execute and save notebook cells, stopping at the first cell error.

    Local execution reuses a detached kernel for this notebook. With --server,
    execution reuses the notebook's server session. Cell errors produce a
    nonzero exit status after the updated notebook or cell has been shown.
    """
    state = runtime()
    try:
        errors = await execute_notebook(
            state.path(path), cell_id, state.settings, timeout, kernel_name, bool(state.server)
        )
        state.notify(path)
    except Exception as error:
        raise operation_error(error, "executing notebook") from error
    await show(path, as_json=as_json, cell_id=cell_id, timeout=timeout)
    if errors:
        raise CommandError(f"{errors[0]['ename']}: {errors[0]['evalue']}")
