from pathlib import Path
from typing import Callable, Dict, List

from fps import Module
from textual.containers import Container

from txl.base import Editor, Editors, Footer, Header, MainArea


class EditorsMeta(type(Editors), type(Container)):
    pass


class _Editors(Editors, Container, metaclass=EditorsMeta):
    ext_editor_factories: Dict[str, List[Callable[[], Editor]]]

    def __init__(
        self,
        header: Header,
        footer: Footer,
        main_area: MainArea,
    ):
        super().__init__(id="editors")
        self.header = header
        self.footer = footer
        self.main_area = main_area
        self.ext_editor_factories = {}
        self.editor_factories = []

    def register_editor_factory(
        self, editor_factory: Callable[[], Editor], extensions: List[str] = [None]
    ):
        self.editor_factories.append(editor_factory)
        for ext in extensions:
            if ext not in self.ext_editor_factories:
                self.ext_editor_factories[ext] = []
            self.ext_editor_factories[ext].append(editor_factory)

    async def on_open(self, path: str) -> None:
        path = Path(path)
        extension = path.suffix
        for ext, editor_factories in self.ext_editor_factories.items():
            if ext == extension:
                preferred_editor_factory = editor_factories[0]
                break
        else:
            if None not in self.ext_editor_factories:
                raise RuntimeError(f"Could not find an editor for file extension {extension}")
            preferred_editor_factory = self.ext_editor_factories[None][0]
        preferred_editor = preferred_editor_factory()
        self.main_area.show(preferred_editor, path.name)
        bindings = preferred_editor.get_bindings()
        if bindings:
            self.footer.update_bindings(bindings)
        await preferred_editor.open(str(path))
        preferred_editor.refresh(layout=True)


class EditorsModule(Module):
    async def start(self) -> None:
        header = await self.get(Header)
        footer = await self.get(Footer)
        main_area = await self.get(MainArea)
        editors = _Editors(header, footer, main_area)
        self.put(editors, Editors)
