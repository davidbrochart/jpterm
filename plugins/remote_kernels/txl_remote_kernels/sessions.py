"""Manage notebook sessions without opening kernel channels."""

from pathlib import PurePosixPath
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

import anyio
import httpx2


class RemoteSessions:
    def __init__(self, url, timeout=30):
        parsed = urlsplit(url)
        self.base_url = urlunsplit(parsed._replace(query="", fragment="")).rstrip("/")
        self.params = parse_qs(parsed.query)
        self.timeout = timeout

    async def _list(self, client):
        response = await client.get(f"{self.base_url}/api/sessions", params=self.params)
        response.raise_for_status()
        return [session for session in response.json()
                if session.get("type") == "notebook" and session.get("kernel") is not None]

    async def list(self):
        with anyio.fail_after(self.timeout):
            async with httpx2.AsyncClient(timeout=self.timeout) as client:
                sessions = await self._list(client)
        return [
            {"path": session["path"], "kernel_name": session["kernel"]["name"],
             "kernel_id": session["kernel"]["id"], "session_id": session["id"],
             "alive": session["kernel"].get("execution_state") != "dead"}
            for session in sessions
        ]

    async def stop(self, path):
        path = str(PurePosixPath(path)).lstrip("/")
        with anyio.fail_after(self.timeout):
            async with httpx2.AsyncClient(timeout=self.timeout) as client:
                sessions = [session for session in await self._list(client)
                            if session["path"] == path]
                if not sessions:
                    return False
                if len(sessions) > 1:
                    raise ValueError(f"Multiple notebook sessions found for: {path}")
                session_id = quote(sessions[0]["id"], safe="")
                response = await client.delete(
                    f"{self.base_url}/api/sessions/{session_id}", params=self.params,
                )
                response.raise_for_status()
        return True
