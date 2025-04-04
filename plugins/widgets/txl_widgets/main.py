from importlib.metadata import entry_points

from fps import Module
from pycrdt import (
    TransactionEvent,
    YMessageType,
    YSyncMessageType,
    create_sync_message,
    create_update_message,
    handle_sync_message,
)

from txl.base import Kernels, Widgets


class _Widgets:
    def __init__(self):
        self.ydocs = {
            ep.name: ep.load() for ep in entry_points(group="ypywidgets")
        }
        self.widgets = {}

    def comm_open(self, msg, comm) -> None:
        target_name = msg["content"]["target_name"]
        if target_name != "ywidget":
            return

        name = msg["metadata"]["ymodel_name"] + "Model"
        comm_id = msg["content"]["comm_id"]
        self.comm = comm
        model = self.ydocs[name]()
        self.widgets[comm_id] = {"model": model, "comm": comm}
        msg = create_sync_message(model.ydoc)
        comm.send(buffers=[msg])

    def comm_msg(self, msg) -> None:
        comm_id = msg["content"]["comm_id"]
        message = bytes(msg["buffers"][0])
        if message[0] == YMessageType.SYNC:
            ydoc = self.widgets[comm_id]["model"].ydoc
            reply = handle_sync_message(
                message[1:],
                ydoc,
            )
            if reply:
                self.widgets[comm_id]["comm"].send(buffers=[reply])
            if message[1] == YSyncMessageType.SYNC_STEP2:
                ydoc.observe(self._send)

    def _send(self, event: TransactionEvent):
        update = event.update
        message = create_update_message(update)
        try:
            self.comm.send(buffers=[message])
        except BaseException:
            pass


class WidgetsModule(Module):
    async def start(self) -> None:
        kernels = await self.get(Kernels)
        widgets = _Widgets()
        kernels.comm_handlers.append(widgets)

        self.put(widgets, Widgets)
