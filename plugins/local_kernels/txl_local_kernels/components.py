import json
from pathlib import Path
from typing import Any

from asphalt.core import Component, Context, context_teardown
from pycrdt import Map

from txl.base import Kernels, Kernelspecs

from .driver import KernelDriver, kernel_drivers
from .kernelspec import kernelspec_dirs


class LocalKernels(Kernels):
    comm_handlers = []

    def __init__(self, kernel_name: str | None = None):
        self.kernel = KernelDriver(kernel_name, comm_handlers=self.comm_handlers)

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


class LocalKernelspecsComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        kernelspecs = LocalKernelspecs()
        ctx.add_resource(kernelspecs, types=Kernelspecs)
