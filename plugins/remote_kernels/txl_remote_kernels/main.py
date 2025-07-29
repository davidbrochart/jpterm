from __future__ import annotations

from typing import Any
from urllib import parse

import httpx
from anyio import create_task_group, sleep
from fps import Module
from pycrdt import Map

from txl.base import Kernels, Kernelspecs

from .driver import KernelDriver


class RemoteKernels(Kernels):
    comm_handlers = []

    def __init__(
        self,
        url: str,
        kernel_name: str | None,
    ):
        self.kernel = KernelDriver(
            self.task_group, url, kernel_name, comm_handlers=self.comm_handlers
        )

    async def execute(self, ycell: Map):
        await self.kernel.execute(ycell)


class RemoteKernelspecs(Kernelspecs):
    def __init__(
        self,
        url: str,
    ):
        parsed_url = parse.urlparse(url)
        self.base_url = parse.urljoin(url, parsed_url.path).rstrip("/")
        self.query_params = parse.parse_qs(parsed_url.query)
        self.cookies = httpx.Cookies()

    async def get(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/kernelspecs"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    url,
                    params={**self.query_params},
                    cookies=self.cookies,
                )
                d = r.json()
                self.cookies.update(r.cookies)
                return d
        except httpx.ConnectError:
            raise RuntimeError(f"Could not connect to a Jupyter server at {url}")


class RemoteKernelsModule(Module):
    def __init__(self, name: str, url: str = "http://127.0.0.1:8000"):
        super().__init__(name)
        self.url = url

    async def start(self) -> None:
        url = self.url

        async with create_task_group() as self.tg:
            class _RemoteKernels(RemoteKernels):
                task_group = self.tg

                def __init__(self, *args, **kwargs):
                    super().__init__(url, *args, **kwargs)

            self.put(_RemoteKernels, Kernels)
            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        self.tg.cancel_scope.cancel()


class RemoteKernelspecsModule(Module):
    def __init__(self, name: str, url: str = "http://127.0.0.1:8000"):
        super().__init__(name)
        self.url = url

    async def start(self) -> None:
        kernelspecs = RemoteKernelspecs(self.url)
        self.put(kernelspecs, Kernelspecs)
