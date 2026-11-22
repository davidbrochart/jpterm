"""Run jpterm services around a widget hosted by an existing Anytext app."""

from contextlib import asynccontextmanager

import anyio
from txl_jpterm.main import JptermView

from .app import create_app
from .command import operation_error


@asynccontextmanager
async def open_view(host_app, state):
    if state.server:
        directory = state.ctx.resolve(".").lstrip("/") or "."
        settings = [f"file_browser.path={directory}", *state.settings]
    else:
        directory = state.path(".")
        settings = [f"local_contents.root={directory}", *state.settings]
    module = create_app(settings, 30, host_app=host_app)
    stopped = anyio.Event()

    async def serve(*, task_status=anyio.TASK_STATUS_IGNORED):
        # FPS owns its cancel scopes in this task. Once started, keep its
        # services alive until the UI is removed, then stop them normally.
        with anyio.CancelScope() as lifetime:
            async with module:
                if module.exceptions:
                    raise operation_error(module.exceptions[0], "opening interface")
                view = await module.get(JptermView)
                lifetime.shield = True
                task_status.started(view)
                await stopped.wait()

    async with anyio.create_task_group() as task_group:
        try:
            view = await task_group.start(serve)
            yield view
        finally:
            stopped.set()
