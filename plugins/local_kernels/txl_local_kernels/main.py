import json
from pathlib import Path
from typing import Any

from anyio import CancelScope, create_task_group, sleep
from fps import Module
from pycrdt import Map

from txl.base import Kernels, Kernelspecs

from .driver import KernelDriver, kernel_drivers
from .kernelspec import kernelspec_dirs
from .sessions import LocalSession


class LocalKernels(Kernels):
    comm_handlers = []

    def __init__(
        self, kernel_name: str | None = None, kernel_cwd: str = "", connection_file: str = "",
        path: str | None = None,
    ):
        owned_session = None
        if path is not None and not connection_file:
            session = LocalSession(path)
            connection_file = session.connection_file(kernel_name)
            if session.launched:
                owned_session = session
        self.kernel = KernelDriver(
            self.task_group, kernel_name, kernel_cwd=kernel_cwd,
            comm_handlers=self.comm_handlers,
            connection_file=connection_file, write_connection_file=not connection_file,
            launch=not connection_file,
            owned_session=owned_session,
        )

    async def execute(self, ycell: Map):
        await self.kernel.execute(ycell)

    async def aclose(self):
        await self.kernel.stop()


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
        with CancelScope(shield=True):
            for kernel_driver in list(kernel_drivers):
                if kernel_driver.task_group is self.tg:
                    await kernel_driver.stop()
        self.tg.cancel_scope.cancel()


class LocalKernelspecsModule(Module):
    async def start(self) -> None:
        kernelspecs = LocalKernelspecs()
        self.put(kernelspecs, Kernelspecs)
