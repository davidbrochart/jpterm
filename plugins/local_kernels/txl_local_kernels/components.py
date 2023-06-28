import y_py as Y
from asphalt.core import Component, Context, context_teardown

from txl.base import Kernels

from .driver import KernelDriver, kernel_drivers


class LocalKernels(Kernels):

    comm_handlers = []

    def __init__(self, kernel_name: str | None = None):
        self.kernel = KernelDriver(kernel_name, comm_handlers=self.comm_handlers)

    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        await self.kernel.execute(ydoc, ycell)


class LocalKernelsComponent(Component):
    @context_teardown
    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(LocalKernels, types=Kernels)

        yield

        for kernel_driver in kernel_drivers:
            await kernel_driver.stop()
