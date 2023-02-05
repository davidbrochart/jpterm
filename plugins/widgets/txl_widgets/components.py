import asyncio
from functools import partial

import pkg_resources
from asphalt.core import Component, Context
from ypywidgets.yutils import (
    YMessageType,
    YSyncMessageType,
    create_update_message,
    process_sync_message,
    put_updates,
    sync,
)

from txl.base import Kernels, Widgets
from txl.hooks import register_component


class _Widgets:
    def __init__(self):
        self.ydocs = {
            ep.name: ep.load()
            for ep in pkg_resources.iter_entry_points(group="ypywidgets")
        }
        self.widgets = {}
        self._update_queue = asyncio.Queue()  # FIXME: one per widget
        self.synced = asyncio.Event()  # FIXME

    def comm_open(self, msg, comm) -> None:
        name = msg["content"]["target_name"]
        comm_id = msg["content"]["comm_id"]
        self.comm = comm
        model = self.ydocs[name](open_comm=False)
        self.widgets[comm_id] = {"model": model, "comm": comm}
        sync(model.ydoc, comm)
        asyncio.create_task(self._send(model.ydoc))

    def comm_msg(self, msg) -> None:
        comm_id = msg["content"]["comm_id"]
        message = bytes(msg["buffers"][0])
        if message[0] == YMessageType.SYNC:
            process_sync_message(
                message[1:],
                self.widgets[comm_id]["model"].ydoc,
                self.widgets[comm_id]["comm"],
            )
            if message[1] == YSyncMessageType.SYNC_STEP2:
                self.synced.set()

    async def _send(self, ydoc):
        await self.synced.wait()
        ydoc.observe_after_transaction(partial(put_updates, self._update_queue))
        while True:
            update = await self._update_queue.get()
            message = create_update_message(update)
            try:
                self.comm.send(buffers=[message])
            except BaseException:
                pass


class WidgetsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        kernels = await ctx.request_resource(Kernels, "kernels")
        widgets = _Widgets()
        kernels.comm_handlers.append(widgets)

        ctx.add_resource(widgets, name="widgets", types=Widgets)


c = register_component("widgets", WidgetsComponent)
