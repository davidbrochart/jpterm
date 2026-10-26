"""Start, inspect and stop notebook kernels locally or on a Jupyter server."""

import json
from pathlib import PurePosixPath

import anyio
import httpx2
import rich_click as click
from txl_local_kernels.sessions import LocalSession, list_sessions
from txl_remote_kernels.sessions import RemoteSessions

from txl.base import Contents, Kernels

from .app import create_app


def create_notebook_kernel(path, document, kernels, kernel_name=None, remote=False):
    kernel_name = kernel_name or document.source.get("metadata", {}).get(
        "kernelspec", {}
    ).get("name")
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


@click.group()
def kernel():
    """Manage notebook kernels locally or with --server."""


@kernel.command("start")
@click.argument("path")
@click.option("--kernel", "kernel_name", help="Kernel name when starting a new kernel.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to load the notebook and wait for readiness.")
@click.pass_context
def start_kernel(ctx, path, kernel_name, timeout):
    """Start or reuse notebook PATH's kernel without executing or saving cells."""
    remote = bool(ctx.find_root().params["server"])
    try:
        anyio.run(
            start_notebook_kernel, path, ctx.obj["set_"], timeout, kernel_name, remote,
            backend=ctx.obj["backend"],
        )
    except Exception as exc:
        while getattr(exc, "exceptions", None):
            exc = exc.exceptions[0]
        raise click.ClickException(request_error(exc, "starting")) from exc


@kernel.command("list")
@click.option("--json", "as_json", is_flag=True, help="Print session information as JSON.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to list server sessions, in seconds.")
@click.pass_context
def list_kernels(ctx, as_json, timeout):
    """List notebook kernels (including stale local sessions)."""
    server = ctx.find_root().params["server"]
    try:
        sessions = (
            anyio.run(RemoteSessions(server, timeout).list, backend=ctx.obj["backend"])
            if server else list_sessions()
        )
    except Exception as exc:
        raise click.ClickException(request_error(exc, "listing")) from exc
    if as_json:
        click.echo(json.dumps(sessions, indent=2, ensure_ascii=False))
    else:
        for session in sessions:
            state = "running" if session["alive"] else "stale"
            identifier = session["kernel_id"] if server else session["pid"]
            click.echo(f"{session['path']}\t{session['kernel_name']}\t{identifier}\t{state}")


@kernel.command("stop")
@click.argument("path")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=30.0,
              show_default=True, help="Maximum time to stop the kernel, in seconds.")
@click.pass_context
def stop_kernel(ctx, path, timeout):
    """Stop notebook PATH's kernel by removing its local or server session."""
    server = ctx.find_root().params["server"]

    async def stop():
        if server:
            return await RemoteSessions(server, timeout).stop(path)
        with anyio.fail_after(timeout):
            return await LocalSession(path, timeout).stop()

    try:
        stopped = anyio.run(stop, backend=ctx.obj["backend"])
    except Exception as exc:
        raise click.ClickException(request_error(exc, "stopping")) from exc
    if not stopped:
        location = "remote" if server else "local"
        raise click.ClickException(f"No {location} kernel session for: {path}")
