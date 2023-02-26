from typing import Type

import in_n_out as ino
import y_py as Y

from txl.base import Kernels

from .driver import KernelDriver


class LocalKernels(Kernels):

    comm_handlers = []

    def __init__(self, kernel_name: str | None = None):
        self.kernel = KernelDriver(kernel_name, comm_handlers=self.comm_handlers)

    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        await self.kernel.execute(ydoc, ycell)


def local_kernels() -> Type[Kernels]:
    return LocalKernels


ino.register_provider(local_kernels)
