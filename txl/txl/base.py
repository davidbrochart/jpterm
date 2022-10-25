from abc import ABC, abstractmethod
from typing import Union, Callable, List

from asphalt.core import Event, Signal



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


class Editors(ABC):
    @abstractmethod
    def register_editor_factory(self, editor_factory: Callable, extensions: List[str] = [None]):
        ...

    @abstractmethod
    async def on_open(self, event: FileOpenEvent) -> None:
        ...


class Contents(ABC):
    @abstractmethod
    async def get_content(self, path: str, is_dir: bool = True) -> Union[List, str]:
        ...
