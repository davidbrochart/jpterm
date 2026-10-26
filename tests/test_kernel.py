from unittest.mock import AsyncMock, patch

import anyio
import httpx2
import pytest
from jpterm.kernel import request_error
from txl_remote_kernels.sessions import RemoteSessions


def test_remote_sessions_preserve_base_path_and_authentication():
    async def check():
        sessions = [
            {"id": "session/id", "path": "folder/test.ipynb", "type": "notebook",
             "kernel": {"id": "kernel-id", "name": "python3", "execution_state": "idle"}},
            {"id": "console", "path": "console", "type": "console",
             "kernel": {"id": "console-kernel", "name": "python3"}},
        ]
        response = httpx2.Response(
            200, json=sessions, request=httpx2.Request("GET", "http://server/base/api/sessions")
        )
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = response
        client.delete.return_value = httpx2.Response(
            204, request=httpx2.Request("DELETE", "http://server/base/api/sessions/session%2Fid")
        )
        manager = RemoteSessions("http://server/base/?token=secret")
        with patch("txl_remote_kernels.sessions.httpx2.AsyncClient", return_value=client):
            assert await manager.list() == [{
                "path": "folder/test.ipynb", "kernel_name": "python3",
                "kernel_id": "kernel-id", "session_id": "session/id", "alive": True,
            }]
            client.get.assert_awaited_once_with(
                "http://server/base/api/sessions", params={"token": ["secret"]}
            )
            assert await manager.stop("./folder/test.ipynb")
            client.delete.assert_awaited_once_with(
                "http://server/base/api/sessions/session%2Fid", params={"token": ["secret"]}
            )
            client.delete.reset_mock()
            assert not await manager.stop("missing.ipynb")
            client.delete.assert_not_awaited()
            client.get.return_value = httpx2.Response(
                200, json=[sessions[0], dict(sessions[0], id="duplicate")],
                request=response.request,
            )
            with pytest.raises(ValueError, match="Multiple notebook sessions"):
                await manager.stop("folder/test.ipynb")
            client.delete.assert_not_awaited()

    anyio.run(check)


@pytest.mark.parametrize("action", ["list", "stop"])
def test_remote_sessions_report_http_errors(action):
    async def check():
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = httpx2.Response(
            403, request=httpx2.Request("GET", "http://server/api/sessions?token=secret")
        )
        with patch("txl_remote_kernels.sessions.httpx2.AsyncClient", return_value=client):
            manager = RemoteSessions("http://server/?token=secret")
            with pytest.raises(httpx2.HTTPStatusError) as caught:
                if action == "list":
                    await manager.list()
                else:
                    await manager.stop("test.ipynb")
            assert request_error(caught.value, action) == "Remote kernel request failed (HTTP 403)"
            client.delete.assert_not_awaited()

    anyio.run(check)
