from kernel_driver import KernelDriver  # type: ignore


class Kernels:
    def KernelDriver(self, *args, **kwargs):
        kernel_name = kwargs.get("kernel_name", "")
        return KernelDriver(kernel_name=kernel_name, log=False)
