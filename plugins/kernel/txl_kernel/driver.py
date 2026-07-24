import math
import time
from typing import Any, Dict

from anyio import Event, create_memory_object_stream, move_on_after
from fps import Signal
from pycrdt import Array, Map

from txl.stapled import StapledObjectStream

from .message import create_message


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.monotonic())


class Comm:
    def __init__(self, comm_id: str, shell_channel, session_id: str, send_message, task_group):
        self.comm_id = comm_id
        self.shell_channel = shell_channel
        self.session_id = session_id
        self.send_message = send_message
        self.task_group = task_group
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
        self.task_group.create_task(
            self.send_message(msg, self.shell_channel, change_date_to_str=True)
        )


class KernelMixin:
    def __init__(self, task_group):
        self.task_group = task_group
        self.busy = Signal[bool]()
        self.msg_cnt = 0
        self.execute_requests: Dict[str, Dict[str, StapledObjectStream]] = {}
        self.recv_queue = StapledObjectStream(
            *create_memory_object_stream[Any](max_buffer_size=math.inf)
        )
        self.started = Event()
        task_group.create_task(self.recv())

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
                "iopub": StapledObjectStream(
                    *create_memory_object_stream[Any](max_buffer_size=math.inf)
                ),
                "shell": StapledObjectStream(
                    *create_memory_object_stream[Any](max_buffer_size=math.inf)
                ),
            }
            with move_on_after(new_timeout) as scope:
                msg = await self.execute_requests[msg_id]["shell"].receive()
            if scope.cancelled_caught:
                del self.execute_requests[msg_id]
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["header"]["msg_type"] == "kernel_info_reply":
                with move_on_after(0.2) as scope:
                    msg = await self.execute_requests[msg_id]["iopub"].receive()
                if not scope.cancelled_caught:
                    break
            del self.execute_requests[msg_id]
            new_timeout = deadline_to_timeout(deadline)

    async def recv(self):
        while True:
            msg = await self.recv_queue.receive()
            channel = msg.pop("channel")
            msg_type = msg["header"]["msg_type"]
            if msg_type == "comm_open":
                for comm_handler in self.comm_handlers:
                    comm_id = msg["content"]["comm_id"]
                    comm = Comm(
                        comm_id,
                        self.shell_channel,
                        self.session_id,
                        self.send_message,
                        self.task_group,
                    )
                    comm_handler.comm_open(msg, comm)
            elif msg_type == "comm_msg":
                for comm_handler in self.comm_handlers:
                    comm_handler.comm_msg(msg)
            elif msg_type == "status":
                execution_state = msg["content"]["execution_state"]
                if execution_state == "idle":
                    await self.busy.emit(False)
                elif execution_state == "busy":
                    await self.busy.emit(True)
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests:
                # msg["header"] = str_to_date(msg["header"])
                # msg["parent_header"] = str_to_date(msg["parent_header"])
                self.execute_requests[msg_id][channel].send_nowait(msg)

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
        ycell["execution_count"] = None
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
            "iopub": StapledObjectStream(
                *create_memory_object_stream[Any](max_buffer_size=math.inf)
            ),
            "shell": StapledObjectStream(
                *create_memory_object_stream[Any](max_buffer_size=math.inf)
            ),
        }
        await self.send_message(msg, self.shell_channel, change_date_to_str=True)
        if wait_for_executed:
            deadline = time.monotonic() + timeout
            while True:
                with move_on_after(deadline_to_timeout(deadline)) as scope:
                    msg = await self.execute_requests[msg_id]["iopub"].receive()
                if scope.cancelled_caught:
                    del self.execute_requests[msg_id]
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    raise RuntimeError(error_message)
                await self._handle_outputs(ycell["outputs"], msg)
                if (
                    (msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle")
                ):
                    break
            with move_on_after(deadline_to_timeout(deadline)) as scope:
                msg = await self.execute_requests[msg_id]["shell"].receive()
            if scope.cancelled_caught:
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
                if (not outputs) or (outputs[-1].get("name") != content["name"]):  # type: ignore
                    outputs.append(
                        Map(
                            {
                                "name": content["name"],
                                "output_type": msg_type,
                                "text": Array([content["text"]]),
                            }
                        )
                    )
                else:
                    outputs[-1]["text"].append(content["text"])  # type: ignore
        elif msg_type == "display_data":
            outputs.append(
                {
                    "data": content["data"],
                    "metadata": {},
                    "output_type": msg_type,
                }
            )
        elif msg_type == "execute_result":
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
