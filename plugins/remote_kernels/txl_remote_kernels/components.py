import y_py as Y
from asphalt.core import Component, Context

from txl.base import Kernels
from txl.hooks import register_component

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

        ctx.add_resource(_RemoteKernels, name="kernels", types=Kernels)


c = register_component("kernels", RemoteKernelsComponent)
