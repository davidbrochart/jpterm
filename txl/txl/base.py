from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Union

import y_py as Y
from asphalt.core import Event, Signal
from textual.binding import Binding


class FileOpenEvent(Event):
    def __init__(self, source, topic, path):
        super().__init__(source, topic)
        self.path = path


class FileBrowser(ABC):
    open_file_signal = Signal(FileOpenEvent)

    @abstractmethod
    async def load_directory(self, node) -> None:
        ...


class Editor(ABC):
    @abstractmethod
    async def open(self, path: str) -> None:
        ...

    def get_bindings(self) -> List[Binding] | None:
        return None


class Editors(ABC):
    @abstractmethod
    def register_editor_factory(
        self, editor_factory: Callable, extensions: List[str] = [None]
    ):
        ...

    @abstractmethod
    async def on_open(self, event: FileOpenEvent) -> None:
        ...


class Contents(ABC):
    @abstractmethod
    async def get(
        self,
        path: str,
        is_dir: bool = True,
        type: str = "text",
    ) -> Union[List, str, bytes, Dict[str, Any]]:
        ...


class Cell(ABC):
    @property
    @abstractmethod
    def update(self):
        ...


CellFactory = Callable[[], Cell]


class Kernel(ABC):
    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        ...


class Kernels(ABC):
    @abstractmethod
    def __init__(self, kernel_name: str | None):
        ...

    @abstractmethod
    async def execute(self, ydoc: Y.YDoc, ycell: Y.YMap):
        ...


class Notebook(ABC):
    ...


NotebookFactory = Callable[[Dict[str, Any] | None], Notebook]


class Header(ABC):
    ...


class Footer(ABC):
    ...


class MainArea(ABC):
    @abstractmethod
    def show(self, widget):
        ...


class Terminals(ABC):
    @abstractmethod
    async def open(self):
        ...


class Terminal(ABC):
    ...


TerminalFactory = Callable[[int, int], Terminal]


class Launcher(ABC):
    @abstractmethod
    def register(self, i: str, document):
        ...


class Widgets(ABC):
    @abstractmethod
    def comm_open(self, msg, comm) -> None:
        ...

    @abstractmethod
    def comm_msg(self, msg) -> None:
        ...
