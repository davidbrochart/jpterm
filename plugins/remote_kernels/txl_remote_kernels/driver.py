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

from .message import from_binary, to_binary


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
        self.ws_url = ("wss" if self.base_url[i - 1] == "s" else "ws") + self.base_url[
            i:
        ]
        self.start_task = asyncio.create_task(self.start())
        self.comm_handlers = comm_handlers
        self.shell_channel = "shell"
        self.control_channel = "control"
        self.iopub_channel = "iopub"

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
            response = r.json()
            self.cookies.update(r.cookies)
            self.session_id = response["id"]
            kernel_id = response["kernel"]["id"]
            response = await client.get(
                f"{self.base_url}/api/kernels/{kernel_id}",
                cookies=self.cookies,
            )
        if response.status_code != 200 or kernel_id != response.json()["id"]:
            return
        async with aconnect_ws(
            f"{self.ws_url}/api/kernels/{kernel_id}/channels",
            params={"session_id": self.session_id},
            cookies=self.cookies,
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
            if isinstance(message.data, str):
                message = json.loads(message.data)
            else:
                message = from_binary(message.data)
            self.recv_queue.put_nowait(message)

    async def send_message(
        self,
        msg: Dict[str, Any],
        channel,
        change_date_to_str: bool = False,
    ):
        _date_to_str = date_to_str if change_date_to_str else lambda x: x
        msg["header"] = _date_to_str(msg["header"])
        msg["parent_header"] = _date_to_str(msg["parent_header"])
        msg["metadata"] = _date_to_str(msg["metadata"])
        msg["content"] = _date_to_str(msg.get("content", {}))
        msg["channel"] = channel
        bmsg = to_binary(msg)
        if bmsg is None:
            await self.websocket.send_json(msg)
        else:
            await self.websocket.send_bytes(bmsg)
