import json
from pathlib import Path
from typing import Any

from anyio import create_task_group, sleep
from fps import Module
from pycrdt import Map

from txl.base import Kernels, Kernelspecs

from .driver import KernelDriver, kernel_drivers
from .kernelspec import kernelspec_dirs


class LocalKernels(Kernels):
    comm_handlers = []

    def __init__(self, kernel_name: str | None = None):
        self.kernel = KernelDriver(self.task_group, kernel_name, comm_handlers=self.comm_handlers)

    async def execute(self, ycell: Map):
        await self.kernel.execute(ycell)


class LocalKernelspecs(Kernelspecs):
    async def get(self) -> dict[str, Any]:
        kernelspecs = {}
        for search_path in kernelspec_dirs():
            for path in Path(search_path).glob("*/kernel.json"):
                with open(path) as f:
                    spec = json.load(f)
                name = path.parent.name
                kernelspecs[name] = {"name": name, "spec": spec}
        return {"kernelspecs": kernelspecs}


class LocalKernelsModule(Module):
    async def start(self) -> None:

        async with create_task_group() as self.tg:
            class _LocalKernels(LocalKernels):
                task_group = self.tg

            self.put(_LocalKernels, Kernels)
            self.done()
            await sleep(float("inf"))

    async def stop(self) -> None:
        for kernel_driver in kernel_drivers:
            self.tg.start_soon(kernel_driver.stop)
        self.tg.cancel_scope.cancel()


class LocalKernelspecsModule(Module):
    async def start(self) -> None:
        kernelspecs = LocalKernelspecs()
        self.put(kernelspecs, Kernelspecs)
