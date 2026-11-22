"""Start, inspect and stop notebook kernels locally or on a Jupyter server."""

import json
from pathlib import PurePosixPath
from typing import Annotated

import anyio
import httpx2
from cyclopts import App, Parameter
from txl_local_kernels.sessions import LocalSession, list_sessions
from txl_remote_kernels.sessions import RemoteSessions

from txl.base import Contents, Kernels

from .app import create_app
from .command import CommandError, Timeout, runtime


def create_notebook_kernel(path, document, kernels, kernel_name=None, remote=False):
    kernel_name = kernel_name or document.source.get("metadata", {}).get("kernelspec", {}).get(
        "name"
    )
    if remote:
        return kernels(kernel_name, path=str(PurePosixPath(path)).lstrip("/"))
    connection_file = LocalSession(path).connection_file(kernel_name)
    return kernels(kernel_name, connection_file=connection_file)


async def start_notebook_kernel(path, settings, timeout, kernel_name=None, remote=False):
    if PurePosixPath(path).suffix != ".ipynb":
        raise ValueError("Starting a kernel requires a notebook (.ipynb).")
    module = create_app(settings, timeout)
    deadline = anyio.current_time() + timeout
    async with module:
        with anyio.fail_after(max(0, deadline - anyio.current_time())):
            contents = await module.get(Contents)
            document = await contents.get(path, type="notebook")
            kernels = await module.get(Kernels)
            client = create_notebook_kernel(path, document, kernels, kernel_name, remote)
            try:
                await client.kernel.started.wait()
            finally:
                if not remote:
                    with anyio.CancelScope(shield=True):
                        await client.aclose()


def request_error(exc, action):
    if isinstance(exc, (TimeoutError, httpx2.TimeoutException)):
        return f"Timed out {action} kernels"
    if isinstance(exc, httpx2.HTTPStatusError):
        return f"Remote kernel request failed (HTTP {exc.response.status_code})"
    if isinstance(exc, httpx2.ConnectError):
        return "Could not connect to the Jupyter server"
    return str(exc)


kernel = App(
    name="kernel", help="Manage notebook kernels locally or with --server.", version_flags=()
)


@kernel.command(name="start")
async def start_kernel(
    path: str,
    *,
    kernel_name: Annotated[
        str | None, Parameter(name="--kernel", help="Kernel name when starting a new kernel.")
    ] = None,
    timeout: Timeout = 30.0,
):
    """Start or reuse notebook PATH's kernel without executing or saving cells."""
    state = runtime()
    try:
        await start_notebook_kernel(
            state.path(path), state.settings, timeout, kernel_name, bool(state.server)
        )
    except Exception as error:
        while isinstance(error, ExceptionGroup):
            error = error.exceptions[0]
        raise CommandError(request_error(error, "starting")) from error


@kernel.command(name="list")
async def list_kernels(
    *,
    as_json: Annotated[
        bool, Parameter(name="--json", help="Print session information as JSON.")
    ] = False,
    timeout: Timeout = 30.0,
):
    """List notebook kernels, including stale local sessions."""
    state = runtime()
    try:
        sessions = (
            await RemoteSessions(state.server, timeout).list() if state.server else list_sessions()
        )
    except Exception as error:
        raise CommandError(request_error(error, "listing")) from error
    if as_json:
        await state.emit(json.dumps(sessions, indent=2, ensure_ascii=False))
    else:
        for session in sessions:
            if not state.is_terminal:
                await state.emit(session)
            else:
                status = "running" if session["alive"] else "stale"
                identifier = session["kernel_id"] if state.server else session["pid"]
                await state.emit(
                    f"{session['path']}\t{session['kernel_name']}\t{identifier}\t{status}"
                )


@kernel.command(name="stop")
async def stop_kernel(path: str, *, timeout: Timeout = 30.0):
    """Stop notebook PATH's kernel by removing its local or server session."""
    state = runtime()
    try:
        path = state.path(path)
        if state.server:
            stopped = await RemoteSessions(state.server, timeout).stop(path)
        else:
            with anyio.fail_after(timeout):
                stopped = await LocalSession(path, timeout).stop()
    except Exception as error:
        raise CommandError(request_error(error, "stopping")) from error
    if not stopped:
        location = "remote" if state.server else "local"
        raise CommandError(f"No {location} kernel session for: {path}")
