import asyncio
import time
import uuid
from typing import Dict, List
from urllib import parse

import httpx
import y_py as Y
from httpx_ws import WebSocketNetworkError, aconnect_ws

from .message import create_message, send_message, str_to_date


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


class KernelDriver:
    def __init__(
        self,
        url: str,
        kernel_name: str = "",
    ) -> None:
        self.kernel_name = kernel_name
        parsed_url = parse.urlparse(url)
        self.base_url = parse.urljoin(url, parsed_url.path).rstrip("/")
        self.query_params = parse.parse_qs(parsed_url.query)
        self.cookies = httpx.Cookies()
        i = self.base_url.find(":")
        self.ws_url = ("wss" if self.base_url[i - 1] == "s" else "ws") + self.base_url[
            i:
        ]
        self.msg_cnt = 0
        self.execute_requests: Dict[str, Dict[str, List[asyncio.Future]]] = {}
        self.started = asyncio.Event()
        self.start_task = asyncio.create_task(self.start())

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
                await self._wait_for_ready()
                await asyncio.Future()
            except BaseException:
                recv_task.cancel()
                self.start_task.cancel()

    async def _recv(self):
        try:
            while True:
                message = await self.websocket.receive_json()
                channel = message.pop("channel")
                message["header"] = str_to_date(message["header"])
                message["parent_header"] = str_to_date(message["parent_header"])
                msg_id = message["parent_header"].get("msg_id")
                if msg_id in self.execute_requests:
                    future_messages = self.execute_requests[msg_id][channel]
                    if future_messages:
                        fut = future_messages[-1]
                        if fut.done():
                            fut = asyncio.Future()
                            future_messages.append(fut)
                    else:
                        fut = asyncio.Future()
                        future_messages.append(fut)
                    fut.set_result(message)
        except WebSocketNetworkError:
            pass

    async def _wait_for_ready(self, timeout: float = float("inf")):
        deadline = time.time() + timeout
        new_timeout = timeout
        while True:
            msg = create_message(
                "kernel_info_request",
                session_id=self.session_id,
                msg_id=str(self.msg_cnt),
            )
            self.msg_cnt += 1
            await send_message(msg, "shell", self.websocket, change_date_to_str=True)
            msg_id = msg["header"]["msg_id"]
            self.execute_requests[msg_id] = {
                "iopub": [asyncio.Future()],
                "shell": [asyncio.Future()],
            }
            try:
                msg = await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell"][0], new_timeout
                )
            except asyncio.TimeoutError:
                del self.execute_requests[msg_id]
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["header"]["msg_type"] == "kernel_info_reply":
                try:
                    msg = await asyncio.wait_for(
                        self.execute_requests[msg_id]["iopub"][0], 0.2
                    )
                except asyncio.TimeoutError:
                    pass
                else:
                    break
            del self.execute_requests[msg_id]
            new_timeout = deadline_to_timeout(deadline)
        self.started.set()

    async def execute(
        self,
        ydoc: Y.YDoc,
        ycell: Y.YMap,
        timeout: float = float("inf"),
        msg_id: str = "",
        wait_for_executed: bool = True,
    ) -> None:
        await self.started.wait()
        if ycell["cell_type"] != "code":
            return
        code = str(ycell["source"])
        content = {"code": code, "silent": False}
        msg = create_message(
            "execute_request",
            content,
            session_id=self.session_id,
            msg_id=str(self.msg_cnt),
        )
        if msg_id:
            msg["header"]["msg_id"] = msg_id
        else:
            msg_id = msg["header"]["msg_id"]
        self.msg_cnt += 1
        await send_message(msg, "shell", self.websocket, change_date_to_str=True)
        if wait_for_executed:
            deadline = time.time() + timeout
            self.execute_requests[msg_id] = {
                "iopub": [asyncio.Future()],
                "shell": [asyncio.Future()],
            }
            try:
                await asyncio.wait_for(
                    self.execute_requests[msg_id]["iopub"][0],
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                del self.execute_requests[msg_id]
                raise RuntimeError(error_message)
            await self._handle_outputs(
                ydoc, ycell, self.execute_requests[msg_id]["iopub"]
            )
            try:
                await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell"][0],
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                del self.execute_requests[msg_id]
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            msg = self.execute_requests[msg_id]["shell"][0].result()
            with ydoc.begin_transaction() as txn:
                ycell.set(txn, "execution_count", msg["content"]["execution_count"])
            del self.execute_requests[msg_id]

    async def _handle_outputs(
        self, ydoc: Y.YDoc, ycell: Y.YMap, future_messages: List[asyncio.Future]
    ):
        with ydoc.begin_transaction() as txn:
            ycell.set(txn, "outputs", [])

        while True:
            if not future_messages:
                future_messages.append(asyncio.Future())
            fut = future_messages[0]
            if not fut.done():
                await fut
            future_messages.pop(0)
            msg = fut.result()
            msg_type = msg["header"]["msg_type"]
            content = msg["content"]
            outputs = list(ycell["outputs"])
            if msg_type == "stream":
                if (len(outputs) == 0) or (outputs[-1]["name"] != content["name"]):
                    outputs.append(
                        {"name": content["name"], "output_type": msg_type, "text": []}
                    )
                outputs[-1]["text"].append(content["text"])
            elif msg_type in ("display_data", "execute_result"):
                outputs.append(
                    {
                        "data": {"text/plain": [content["data"].get("text/plain", "")]},
                        "execution_count": content["execution_count"],
                        "metadata": {},
                        "output_type": msg_type,
                    }
                )
            elif msg_type == "error":
                outputs.append(
                    {
                        "ename": content["ename"],
                        "evalue": content["evalue"],
                        "output_type": "error",
                        "traceback": content["traceback"],
                    }
                )
            elif msg_type == "status" and msg["content"]["execution_state"] == "idle":
                break

            with ydoc.begin_transaction() as txn:
                ycell.set(txn, "outputs", outputs)
