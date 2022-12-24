from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union

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
    def register_editor_factory(self, editor_factory: Callable, extensions: List[str] = [None]):
        ...

    @abstractmethod
    async def on_open(self, event: FileOpenEvent) -> None:
        ...


class Contents(ABC):
    @abstractmethod
    async def get(self, path: str, is_dir: bool = True, on_change: Optional[Callable] = None) -> Union[List, str]:
        ...

    @abstractmethod
    def on_change(self, jupyter_ydoc, on_change: Callable, events) -> None:
        ...


class Cell(ABC):
    @property
    @abstractmethod
    def source(self) -> List[str]:
        ...

    @source.setter
    @abstractmethod
    def source(self, value: List[str]):
        ...

    @property
    @abstractmethod
    def outputs(self) -> List[Dict[str, Any]]:
        ...

    @source.setter
    @abstractmethod
    def outputs(self, value: List[Dict[str, Any]]):
        ...


CellFactory = Callable[[], Cell]


class Notebook(ABC):
    @abstractmethod
    def set(self, value: Dict[str, Any]):
        ...


NotebookFactory = Callable[[], Notebook]


class Header(ABC):
    ...


class Footer(ABC):
    ...


class MainArea(ABC):
    ...


class Terminals(ABC):
    @abstractmethod
    async def open(self):
        ...
