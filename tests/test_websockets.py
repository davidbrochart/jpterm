"""Exercise the remote transports with HTTPX2's native WebSocket client."""

from copy import deepcopy
from types import SimpleNamespace

import anyio
import httpx2
import pytest
from httpx2.websockets import ASGIWebSocketTransport
from pycrdt import Doc, Text, handle_sync_message
from txl_remote_contents.main import RemoteContents
from txl_remote_kernels.driver import KernelDriver
from txl_remote_terminals.main import RemoteTerminals


def client_factory(app):
    client_class = httpx2.AsyncClient

    def create(**kwargs):
        return client_class(transport=ASGIWebSocketTransport(app), **kwargs)

    return create


def test_contents_websocket_sync(monkeypatch):
    server_doc = Doc()
    server_doc["source"] = Text("Synchronized through HTTPX2")

    async def app(scope, receive, send):
        assert scope["path"] == "/api/collaboration/room/test-room"
        assert scope["query_string"] == b"sessionId=test-session"
        assert b"session-cookie=yes" in dict(scope["headers"])[b"cookie"]
        assert (await receive())["type"] == "websocket.connect"
        await send({"type": "websocket.accept"})
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            reply = handle_sync_message(event["bytes"][1:], server_doc)
            if reply is not None:
                await send({"type": "websocket.send", "bytes": reply})

    monkeypatch.setattr(httpx2, "AsyncClient", client_factory(app))

    async def check():
        client_doc = Doc()
        client_doc["source"] = Text()
        synced = anyio.Event()
        finished = anyio.Event()
        monkeypatch.setattr("txl_remote_contents.main.sleep_forever", finished.wait)
        with anyio.fail_after(3):
            async with anyio.create_task_group() as tasks:
                contents = RemoteContents(
                    "http://server", {}, httpx2.Cookies({"session-cookie": "yes"}), True, tasks,
                )
                tasks.start_soon(
                    contents.websocket_provider, "test-room", client_doc, "test-session", synced,
                )
                await synced.wait()
                assert str(client_doc["source"]) == "Synchronized through HTTPX2"
                finished.set()

    anyio.run(check)


@pytest.mark.parametrize("protocol", [None, "v1.kernel.websocket.jupyter.org"])
@pytest.mark.parametrize("buffers", [[], [b"binary kernel buffer"]])
def test_kernel_websocket_roundtrip(monkeypatch, protocol, buffers):
    async def app(scope, receive, send):
        assert scope["path"] == "/api/kernels/test-kernel/channels"
        assert scope["query_string"] == b"session_id=test-session"
        assert scope["subprotocols"] == ["v1.kernel.websocket.jupyter.org"]
        assert b"session-cookie=yes" in dict(scope["headers"])[b"cookie"]
        assert (await receive())["type"] == "websocket.connect"
        await send({"type": "websocket.accept", "subprotocol": protocol})
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            payload = {key: event[key] for key in ("text", "bytes") if event.get(key) is not None}
            await send({"type": "websocket.send", **payload})

    monkeypatch.setattr(httpx2, "AsyncClient", client_factory(app))

    async def check():
        driver = KernelDriver.__new__(KernelDriver)
        driver.send_lock = anyio.Lock()
        sender, receiver = anyio.create_memory_object_stream(1)
        driver.recv_queue = SimpleNamespace(send_nowait=sender.send_nowait)
        with anyio.fail_after(3):
            async with httpx2.AsyncClient(cookies={"session-cookie": "yes"}) as client:
                async with client.websocket(
                    "ws://server/api/kernels/test-kernel/channels",
                    params={"session_id": "test-session"},
                    subprotocols=["v1.kernel.websocket.jupyter.org"],
                ) as driver.websocket:
                    async with sender, receiver, anyio.create_task_group() as tasks:
                        tasks.start_soon(driver._recv)
                        message = {
                            "header": {"msg_type": "execute_request", "msg_id": "request"},
                            "parent_header": {}, "metadata": {}, "content": {"code": "1 + 1"},
                            "buffers": buffers, "channel": "shell",
                        }
                        await driver.send_message(deepcopy(message), "shell")
                        assert await receiver.receive() == message
                        tasks.cancel_scope.cancel()

    anyio.run(check)


def test_terminal_websocket_roundtrip(monkeypatch):
    async def app(scope, receive, send):
        assert scope["path"] == "/terminals/websocket/test-terminal"
        assert b"session-cookie=yes" in dict(scope["headers"])[b"cookie"]
        assert (await receive())["type"] == "websocket.connect"
        await send({"type": "websocket.accept"})
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            await send({"type": "websocket.send", "text": event["text"]})

    monkeypatch.setattr(httpx2, "AsyncClient", client_factory(app))

    async def check():
        outgoing, send_queue = anyio.create_memory_object_stream(1)
        recv_queue, incoming = anyio.create_memory_object_stream(1)
        with anyio.fail_after(3):
            async with httpx2.AsyncClient(cookies={"session-cookie": "yes"}) as client:
                async with client.websocket("ws://server/terminals/websocket/test-terminal") as ws:
                    terminal = SimpleNamespace(
                        websocket=ws, _send_queue=send_queue, _recv_queue=recv_queue,
                        _done=anyio.Event(),
                    )
                    async with outgoing, send_queue, recv_queue, incoming:
                        async with anyio.create_task_group() as tasks:
                            terminal.send_task = tasks.create_task(RemoteTerminals._send(terminal))
                            tasks.start_soon(RemoteTerminals._recv, terminal)
                            message = ["stdin", "terminal input\n"]
                            await outgoing.send(message)
                            assert await incoming.receive() == message
                            tasks.cancel_scope.cancel()

    anyio.run(check)
