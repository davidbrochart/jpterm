import asyncio
import json
import time
import uuid
from typing import Any, Dict
from urllib import parse

import httpx
from httpx_ws import aconnect_ws
from txl_kernel.driver import KernelMixin
from txl_kernel.message import date_to_str

from .message import (
    deserialize_msg_from_ws_v1,
    from_binary,
    serialize_msg_to_ws_v1,
    to_binary,
)


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


class KernelDriver(KernelMixin):
    def __init__(
        self,
        url: str,
        kernel_name: str | None = "",
        comm_handlers=[],
    ) -> None:
        super().__init__()
        self.kernel_name = kernel_name
        parsed_url = parse.urlparse(url)
        self.base_url = parse.urljoin(url, parsed_url.path).rstrip("/")
        self.query_params = parse.parse_qs(parsed_url.query)
        self.cookies = httpx.Cookies()
        i = self.base_url.find(":")
        self.ws_url = ("wss" if self.base_url[i - 1] == "s" else "ws") + self.base_url[i:]
        self.start_task = asyncio.create_task(self.start())
        self.comm_handlers = comm_handlers
        self.shell_channel = "shell"
        self.control_channel = "control"
        self.iopub_channel = "iopub"
        self.send_lock = asyncio.Lock()
        self.kernel_id = None

    async def start(self):
        i = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            body = {
                "kernel": {"name": self.kernel_name},
                "name": i,
                "path": i,
                "type": "notebook",
            }
            r = await client.post(
                f"{self.base_url}/api/sessions",
                json=body,
                params={**self.query_params},
                cookies=self.cookies,
            )
            d = r.json()
            self.cookies.update(r.cookies)
            self.session_id = d["id"]
            self.kernel_id = d["kernel"]["id"]
            r = await client.get(
                f"{self.base_url}/api/kernels/{self.kernel_id}",
                cookies=self.cookies,
            )
        if r.status_code != 200 or self.kernel_id != r.json()["id"]:
            return
        async with aconnect_ws(
            f"{self.ws_url}/api/kernels/{self.kernel_id}/channels",
            params={"session_id": self.session_id},
            cookies=self.cookies,
            subprotocols=["v1.kernel.websocket.jupyter.org"],
        ) as self.websocket:
            recv_task = asyncio.create_task(self._recv())
            try:
                await self.wait_for_ready()
                self.started.set()
                await asyncio.Future()
            except BaseException:
                recv_task.cancel()
                self.start_task.cancel()

    async def _recv(self):
        while True:
            message = await self.websocket.receive()
            if self.websocket.subprotocol == "v1.kernel.websocket.jupyter.org":
                msg = deserialize_msg_from_ws_v1(message.data)
            else:
                if isinstance(message.data, str):
                    msg = json.loads(message.data)
                else:
                    msg = from_binary(message.data)
            self.recv_queue.put_nowait(msg)

    async def send_message(
        self,
        msg: Dict[str, Any],
        channel,
        change_date_to_str: bool = False,
    ):
        async with self.send_lock:
            _date_to_str = date_to_str if change_date_to_str else lambda x: x
            msg["header"] = _date_to_str(msg["header"])
            msg["parent_header"] = _date_to_str(msg["parent_header"])
            msg["metadata"] = _date_to_str(msg["metadata"])
            msg["content"] = _date_to_str(msg.get("content", {}))
            msg["channel"] = channel
            if self.websocket.subprotocol == "v1.kernel.websocket.jupyter.org":
                bmsg = serialize_msg_to_ws_v1(msg)
                await self.websocket.send_bytes(bmsg)
            else:
                bmsg = to_binary(msg)
                if bmsg is None:
                    await self.websocket.send_json(msg)
                else:
                    await self.websocket.send_bytes(bmsg)
