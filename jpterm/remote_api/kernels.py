import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Optional

import httpx
from websockets import connect  # type: ignore

from jpterm.jpterm import BASE_URL
from .models import CreateSession, Session


class KernelDriver:

    session: Session
    shell_channel: asyncio.Queue
    iopub_channel: asyncio.Queue
    web_channel: asyncio.Queue

    def __init__(
        self,
        kernel_name: Optional[str] = None,
        session_name: Optional[str] = None,
        session_path: Optional[str] = None,
        session_type: Optional[str] = None,
    ) -> None:
        self.kernel_name = kernel_name or "python3"
        self.session_name = session_name or ""
        self.session_path = session_path or uuid4().hex
        self.session_type = session_type or ""
        self.shell_channel = asyncio.Queue()
        self.iopub_channel = asyncio.Queue()
        self.web_channel = asyncio.Queue()
        self.execution_done = asyncio.Event()
        self.channel_tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        s = {
            "kernel": {"name": self.kernel_name},
            "name": str(self.session_name),
            "path": self.session_path,
            "type": self.session_type,
        }
        self.session = await create_session(CreateSession(**s))
        await self.open_kernel_channels()
        self.channel_tasks.append(asyncio.create_task(self.listen_server()))
        self.channel_tasks.append(asyncio.create_task(self.listen_client()))

    async def open_kernel_channels(self):
        base_url = "ws" + BASE_URL[BASE_URL.find("://") :]  # noqa
        self.websocket = await connect(
            f"{base_url}/api/kernels/{self.session.kernel.id}/channels?session_id={self.session.id}"
        )
        # send kernel_info_request
        msg = create_message(
            channel="shell", msg_type="kernel_info_request", session=self.session.id
        )
        header = msg["header"]
        await self.websocket.send(json.dumps(msg))
        # receive kernel_info_reply
        while True:
            msg = json.loads(await self.websocket.recv())
            if (
                msg["channel"] == "shell"
                and msg["msg_type"] == "kernel_info_reply"
                and msg["parent_header"] == header
            ):
                if msg["content"]["status"] != "ok":
                    raise RuntimeError("Error connecting to kernel")
                return

    async def stop(self) -> None:
        for task in self.channel_tasks:
            task.cancel()
        await self.websocket.close()
        async with httpx.AsyncClient() as client:
            await client.delete(f"{BASE_URL}/api/sessions/{self.session.id}")

    async def listen_server(self):
        queue = {
            "shell": self.shell_channel,
            "iopub": self.iopub_channel,
        }
        while True:
            msg = json.loads(await self.websocket.recv())
            queue[msg["channel"]].put_nowait(msg)

    async def listen_client(self):
        while True:
            msg, header = await self.web_channel.get()
            await self.websocket.send(msg)
            # receive execute_reply
            while True:
                msg = await self.shell_channel.get()
                if (
                    msg["channel"] == "shell"
                    and msg["msg_type"] == "execute_reply"
                    and msg["parent_header"] == header
                ):
                    self.execution_done.set()
                    if msg["content"]["status"] != "ok":
                        raise RuntimeError("Error executing cell")
                    break

    async def execute(self, code):
        self.execution_done.clear()
        # send execute_request
        content = {
            "allow_stdin": False,
            "code": code,
            "silent": False,
            "stop_on_error": True,
            "store_history": True,
            "user_expressions": {},
        }
        metadata = {
            "cellId": uuid4().hex,
            "deletedCells": [],
            "recordTiming": False,
        }
        msg = create_message(
            channel="shell",
            msg_type="execute_request",
            session=self.session.id,
            content=content,
            metadata=metadata,
        )
        header = msg["header"]
        msg = json.dumps(msg)
        self.web_channel.put_nowait((msg, header))
        await self.execution_done.wait()


def create_message(
    channel: str, msg_type: str, session: str, content={}, metadata={}
) -> Dict[str, Any]:
    msg = {
        "buffers": [],
        "channel": channel,
        "content": content,
        "header": {
            "date": str(datetime.utcnow().replace(tzinfo=timezone.utc)),
            "msg_id": uuid4().hex,
            "msg_type": msg_type,
            "session": session,
            "username": "",
            "version": "5.2",
        },
        "metadata": metadata,
        "parent_header": {},
    }
    return msg


async def create_session(session: CreateSession):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/api/sessions", json=session.dict())
    return Session(**r.json())
