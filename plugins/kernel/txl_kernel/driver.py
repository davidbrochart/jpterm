import asyncio
import time
from typing import Dict

from pycrdt import Array, Map

from .message import create_message


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.monotonic())


class Comm:
    def __init__(self, comm_id: str, shell_channel, session_id: str, send_message):
        self.comm_id = comm_id
        self.shell_channel = shell_channel
        self.session_id = session_id
        self.send_message = send_message
        self.msg_cnt = 0

    def send(self, buffers):
        msg = create_message(
            "comm_msg",
            content={"comm_id": self.comm_id},
            session_id=self.session_id,
            msg_id=self.msg_cnt,
            buffers=buffers,
        )
        self.msg_cnt += 1
        asyncio.create_task(self.send_message(msg, self.shell_channel, change_date_to_str=True))


class KernelMixin:
    def __init__(self):
        self.msg_cnt = 0
        self.execute_requests: Dict[str, Dict[str, asyncio.Queue]] = {}
        self.recv_queue = asyncio.Queue()
        self.started = asyncio.Event()
        asyncio.create_task(self.recv())

    def create_message(self, *args, **kwargs):
        return create_message(*args, **kwargs)

    async def wait_for_ready(self, timeout=float("inf")):
        deadline = time.monotonic() + timeout
        new_timeout = timeout
        while True:
            msg = create_message(
                "kernel_info_request",
                session_id=self.session_id,
                msg_id=str(self.msg_cnt),
            )
            self.msg_cnt += 1
            await self.send_message(msg, self.shell_channel, change_date_to_str=True)
            msg_id = msg["header"]["msg_id"]
            self.execute_requests[msg_id] = {
                "iopub": asyncio.Queue(),
                "shell": asyncio.Queue(),
            }
            try:
                msg = await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell"].get(), new_timeout
                )
            except asyncio.TimeoutError:
                del self.execute_requests[msg_id]
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["header"]["msg_type"] == "kernel_info_reply":
                try:
                    msg = await asyncio.wait_for(self.execute_requests[msg_id]["iopub"].get(), 0.2)
                except asyncio.TimeoutError:
                    pass
                else:
                    break
            del self.execute_requests[msg_id]
            new_timeout = deadline_to_timeout(deadline)

    async def recv(self):
        while True:
            msg = await self.recv_queue.get()
            channel = msg.pop("channel")
            msg_type = msg["header"]["msg_type"]
            if msg_type == "comm_open":
                for comm_handler in self.comm_handlers:
                    comm_id = msg["content"]["comm_id"]
                    comm = Comm(comm_id, self.shell_channel, self.session_id, self.send_message)
                    comm_handler.comm_open(msg, comm)
            elif msg_type == "comm_msg":
                for comm_handler in self.comm_handlers:
                    comm_handler.comm_msg(msg)
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests:
                # msg["header"] = str_to_date(msg["header"])
                # msg["parent_header"] = str_to_date(msg["parent_header"])
                self.execute_requests[msg_id][channel].put_nowait(msg)

    async def execute(
        self,
        ycell: Map,
        timeout: float = float("inf"),
        msg_id: str = "",
        wait_for_executed: bool = True,
    ) -> None:
        await self.started.wait()
        if ycell["cell_type"] != "code":
            return
        ycell["outputs"].clear()
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
        self.execute_requests[msg_id] = {
            "iopub": asyncio.Queue(),
            "shell": asyncio.Queue(),
        }
        await self.send_message(msg, self.shell_channel, change_date_to_str=True)
        if wait_for_executed:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    msg = await asyncio.wait_for(
                        self.execute_requests[msg_id]["iopub"].get(),
                        deadline_to_timeout(deadline),
                    )
                except asyncio.TimeoutError:
                    del self.execute_requests[msg_id]
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    raise RuntimeError(error_message)
                await self._handle_outputs(ycell["outputs"], msg)
                if (
                    (msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle")
                ):
                    break
            try:
                msg = await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell"].get(),
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                del self.execute_requests[msg_id]
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            ycell["execution_count"] = msg["content"]["execution_count"]
        del self.execute_requests[msg_id]

    async def _handle_outputs(self, outputs: Array, msg):
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]
        if msg_type == "stream":
            with outputs.doc.transaction():
                # TODO: uncomment when changes are made in jupyter-ydoc
                if (not outputs) or (outputs[-1]["name"] != content["name"]):  # type: ignore
                    outputs.append(
                        #Map(
                        #    {
                        #        "name": content["name"],
                        #        "output_type": msg_type,
                        #        "text": Array([content["text"]]),
                        #    }
                        #)
                        {
                            "name": content["name"],
                            "output_type": msg_type,
                            "text": [content["text"]],
                        }
                    )
                else:
                    #outputs[-1]["text"].append(content["text"])  # type: ignore
                    last_output = outputs[-1]
                    last_output["text"].append(content["text"])  # type: ignore
                    outputs[-1] = last_output
        elif msg_type in ("display_data", "execute_result"):
            outputs.append(
                {
                    "data": content["data"],
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
