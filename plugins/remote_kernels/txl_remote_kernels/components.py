from functools import partial

import y_py as Y
from asphalt.core import Component, Context

from txl.base import Kernels
from txl.hooks import register_component

from .driver import KernelDriver


class RemoteKernels(Kernels):
    def __init__(
        self,
        url: str,
        kernel_name: str,
    ):
        self.kernel = KernelDriver(url, kernel_name)

    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        await self.kernel.execute(ydoc, ycell)


class RemoteKernelsComponent(Component):
    def __init__(self, url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.url = url

    async def start(
        self,
        ctx: Context,
    ) -> None:
        terminals_factory = partial(RemoteKernels, self.url)
        ctx.add_resource(terminals_factory, name="kernels", types=Kernels)


c = register_component("kernels", RemoteKernelsComponent)
