import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional, cast

from txl_kernel.driver import KernelMixin

from .connect import cfg_t, connect_channel, launch_kernel, read_connection_file
from .connect import write_connection_file as _write_connection_file
from .kernelspec import find_kernelspec
from .message import deserialize, feed_identities, serialize


class KernelDriver(KernelMixin):
    def __init__(
        self,
        kernel_name: str = "",
        kernelspec_path: str = "",
        kernel_cwd: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
        comm_handlers=[],
    ) -> None:
        super().__init__()
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path or find_kernelspec(kernel_name)
        self.kernel_cwd = kernel_cwd
        if not self.kernelspec_path:
            raise RuntimeError(
                "Could not find a kernel, maybe you forgot to install one?"
            )
        if write_connection_file:
            self.connection_file_path, self.connection_cfg = _write_connection_file(
                connection_file
            )
        else:
            self.connection_file_path = connection_file
            self.connection_cfg = read_connection_file(connection_file)
        self.key = cast(str, self.connection_cfg["key"])
        self.session_id = uuid.uuid4().hex
        self.channel_tasks: List[asyncio.Task] = []
        self.comm_handlers = comm_handlers
        asyncio.create_task(self.start())

    async def restart(self, startup_timeout: float = float("inf")) -> None:
        for task in self.channel_tasks:
            task.cancel()
        msg = self.create_message("shutdown_request", content={"restart": True})
        await self.send_message(msg, self.control_channel, change_date_to_str=True)
        while True:
            msg = cast(
                Dict[str, Any],
                await self.receive_message(
                    self.control_channel, change_str_to_date=True
                ),
            )
            if msg["msg_type"] == "shutdown_reply" and msg["content"]["restart"]:
                break
        await self.wait_for_ready(startup_timeout)
        self.channel_tasks = []
        self.listen_channels()

    async def start(
        self, startup_timeout: float = float("inf"), connect: bool = True
    ) -> None:
        self.kernel_process = await launch_kernel(
            self.kernelspec_path,
            self.connection_file_path,
            self.kernel_cwd,
            self.capture_kernel_output,
        )
        if connect:
            await self.connect(startup_timeout)
        self.started.set()

    async def connect(self, startup_timeout: float = float("inf")) -> None:
        self.connect_channels()
        self.listen_channels()
        await self.wait_for_ready(startup_timeout)

    def connect_channels(self, connection_cfg: Optional[cfg_t] = None):
        connection_cfg = connection_cfg or self.connection_cfg
        self.shell_channel = connect_channel("shell", connection_cfg)
        self.control_channel = connect_channel("control", connection_cfg)
        self.iopub_channel = connect_channel("iopub", connection_cfg)

    def listen_channels(self):
        self.channel_tasks.append(asyncio.create_task(self._recv_iopub()))
        self.channel_tasks.append(asyncio.create_task(self._recv_shell()))

    async def stop(self) -> None:
        self.kernel_process.kill()
        await self.kernel_process.wait()
        os.remove(self.connection_file_path)
        for task in self.channel_tasks:
            task.cancel()

    async def _recv_iopub(self):
        while True:
            msg = await self.receive_message(
                self.iopub_channel, change_str_to_date=True
            )
            msg["channel"] = "iopub"
            self.recv_queue.put_nowait(msg)

    async def _recv_shell(self):
        while True:
            msg = await self.receive_message(
                self.shell_channel, change_str_to_date=True
            )
            msg["channel"] = "shell"
            self.recv_queue.put_nowait(msg)

    async def send_message(
        self,
        msg: Dict[str, Any],
        sock,
        change_date_to_str: bool = False,
    ) -> None:
        await sock.send_multipart(
            serialize(msg, self.key, change_date_to_str=change_date_to_str), copy=True
        )

    async def receive_message(
        self,
        sock,
        timeout: float = float("inf"),
        change_str_to_date: bool = False,
    ) -> Optional[Dict[str, Any]]:
        timeout *= 1000  # in ms
        ready = await sock.poll(timeout)
        if ready:
            msg_list = await sock.recv_multipart()
            idents, msg_list = feed_identities(msg_list)
            return deserialize(msg_list, change_str_to_date=change_str_to_date)
        return None
