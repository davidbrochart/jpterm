import asyncio
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Optional

import httpx
from websockets import connect  # type: ignore

from .models import CreateSession, Session


def kernel_driver_factory(
    base_url: str, query_params: Dict[str, List[str]], cookies: httpx.Cookies
):
    class KernelDriver:

        session: Session
        shell_channel: asyncio.Queue
        iopub_channel: asyncio.Queue
        web_channel: asyncio.Queue
        execute_requests: Dict[str, Any]

        def __init__(
            self,
            output_hook=default_output_hook,
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
            self.channel_tasks: List[asyncio.Task] = []
            self.execute_requests = {}
            self.output_hook = output_hook

        async def start(self) -> None:
            s = {
                "kernel": {"name": self.kernel_name},
                "name": str(self.session_name),
                "path": self.session_path,
                "type": self.session_type,
            }
            self.session = await create_session(
                CreateSession(**s), base_url, query_params, cookies
            )
            await self.open_kernel_channels()
            self.channel_tasks.append(asyncio.create_task(self.listen_server()))

        async def open_kernel_channels(self):
            ws_base_url = "ws" + base_url[base_url.find("://") :]
            ws_cookies = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            self.websocket = await connect(
                f"{ws_base_url}/api/kernels/{self.session.kernel.id}/channels?session_id={self.session.id}",  # noqa
                extra_headers=[("Cookie", ws_cookies)],
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
                r = await client.delete(
                    f"{base_url}/api/sessions/{self.session.id}",
                    params=query_params,
                    cookies=cookies,
                )
            cookies.update(r.cookies)

        async def listen_server(self):
            while True:
                msg = json.loads(await self.websocket.recv())
                msg_id = msg["parent_header"].get("msg_id")
                channel = msg["channel"]
                if (
                    msg_id in self.execute_requests.keys()
                    and channel in self.execute_requests[msg_id]
                ):
                    self.execute_requests[msg_id][channel].put_nowait(msg)

        async def execute(self, code, msg_id=None):
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
            if msg_id:
                header["msg_id"] = msg_id
            else:
                msg_id = header["msg_id"]
            self.execute_requests[msg_id] = {
                "iopub": asyncio.Queue(),
                "shell": asyncio.Queue(),
            }
            await self.websocket.send(json.dumps(msg))
            while True:
                msg = await self.execute_requests[msg_id]["iopub"].get()
                self.output_hook(msg)
                if (
                    msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle"
                ):
                    break
            while True:
                msg = await self.execute_requests[msg_id]["shell"].get()
                if (
                    msg["msg_type"] == "execute_reply"
                    and msg["parent_header"] == header
                ):
                    break

    return KernelDriver


class Kernels:
    def __init__(
        self, base_url: str, query_params: Dict[str, List[str]], cookies: httpx.Cookies
    ) -> None:
        self.base_url = base_url
        self.KernelDriver = kernel_driver_factory(base_url, query_params, cookies)


def default_output_hook(msg: Dict[str, Any]) -> None:
    """Default hook for redisplaying plain-text output"""
    msg_type = msg["header"]["msg_type"]
    print(msg_type)
    content = msg["content"]
    if msg_type == "stream":
        stream = getattr(sys, content["name"])
        stream.write(content["text"])
    elif msg_type in ("display_data", "execute_result"):
        sys.stdout.write(content["data"].get("text/plain", ""))
    elif msg_type == "error":
        print("\n".join(content["traceback"]), file=sys.stderr)


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


async def create_session(session: CreateSession, base_url, query_params, cookies):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{base_url}/api/sessions",
            json=session.dict(),
            params=query_params,
            cookies=cookies,
        )
    cookies.update(r.cookies)
    return Session(**r.json())
