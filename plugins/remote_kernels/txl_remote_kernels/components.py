from typing import Any
from urllib import parse

import httpx
import y_py as Y
from asphalt.core import Component, Context

from txl.base import Kernels, Kernelspecs

from .driver import KernelDriver


class RemoteKernels(Kernels):
    comm_handlers = []

    def __init__(
        self,
        url: str,
        kernel_name: str | None,
    ):
        self.kernel = KernelDriver(url, kernel_name, comm_handlers=self.comm_handlers)

    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        await self.kernel.execute(ydoc, ycell)


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
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/kernelspecs",
                params={**self.query_params},
                cookies=self.cookies,
            )
            d = r.json()
            self.cookies.update(r.cookies)
            return d


class RemoteKernelsComponent(Component):
    def __init__(self, url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.url = url

    async def start(
        self,
        ctx: Context,
    ) -> None:
        url = self.url

        class _RemoteKernels(RemoteKernels):
            def __init__(self, *args, **kwargs):
                super().__init__(url, *args, **kwargs)

        ctx.add_resource(_RemoteKernels, types=Kernels)


class RemoteKernelspecsComponent(Component):
    def __init__(self, url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.url = url

    async def start(
        self,
        ctx: Context,
    ) -> None:
        kernelspecs = RemoteKernelspecs(self.url)
        ctx.add_resource(kernelspecs, types=Kernelspecs)
