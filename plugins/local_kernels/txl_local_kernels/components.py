import y_py as Y
from asphalt.core import Component, Context

from txl.base import Kernels
from txl.hooks import register_component

from .driver import KernelDriver


class LocalKernels(Kernels):

    comm_handlers = []

    def __init__(self, kernel_name: str | None = None):
        self.kernel = KernelDriver(kernel_name, comm_handlers=self.comm_handlers)

    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        await self.kernel.execute(ydoc, ycell)


class LocalKernelsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(LocalKernels, name="kernels", types=Kernels)


c = register_component("kernels", LocalKernelsComponent)
