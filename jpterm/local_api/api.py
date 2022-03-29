from .contents import Contents
from .kernels import Kernels


class API:
    def __init__(self) -> None:
        self.contents = Contents()
        self.kernels = Kernels()
