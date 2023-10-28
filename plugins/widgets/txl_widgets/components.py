import pkg_resources
import y_py as Y
from asphalt.core import Component, Context
from ypywidgets.utils import (
    YMessageType,
    YSyncMessageType,
    create_update_message,
    process_sync_message,
    sync,
)

from txl.base import Kernels, Widgets


class _Widgets:
    def __init__(self):
        self.ydocs = {
            ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="ypywidgets")
        }
        self.widgets = {}

    def comm_open(self, msg, comm) -> None:
        target_name = msg["content"]["target_name"]
        if target_name != "ywidget":
            return

        name = msg["metadata"]["ymodel_name"]
        comm_id = msg["content"]["comm_id"]
        self.comm = comm
        model = self.ydocs[name](primary=False)
        self.widgets[comm_id] = {"model": model, "comm": comm}
        msg = sync(model._ydoc)
        comm.send(**msg)

    def comm_msg(self, msg) -> None:
        comm_id = msg["content"]["comm_id"]
        message = bytes(msg["buffers"][0])
        if message[0] == YMessageType.SYNC:
            ydoc = self.widgets[comm_id]["model"]._ydoc
            reply = process_sync_message(
                message[1:],
                ydoc,
            )
            if reply:
                self.widgets[comm_id]["comm"].send(buffers=[reply])
            if message[1] == YSyncMessageType.SYNC_STEP2:
                ydoc.observe_after_transaction(self._send)

    def _send(self, event: Y.AfterTransactionEvent):
        update = event.get_update()
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
        kernels = await ctx.request_resource(Kernels)
        widgets = _Widgets()
        kernels.comm_handlers.append(widgets)

        ctx.add_resource(widgets, types=Widgets)
