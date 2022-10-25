from pathlib import Path
from typing import Callable, Dict, List

from asphalt.core import Component, Context
from textual.containers import Container
from txl.base import Editor, Editors, FileOpenEvent
from txl.hooks import register_component


class EditorsMeta(type(Editors), type(Container)):
    pass


class _Editors(Editors, Container, metaclass=EditorsMeta):
    ext_editor_factories: Dict[str, List[Callable[[], Editor]]]

    def __init__(self):
        super().__init__(id="editors")
        self.ext_editor_factories = {}
        self.editor_factories = []

    def register_editor_factory(self, editor_factory: Callable[[], Editor], extensions: List[str] = [None]):
        self.editor_factories.append(editor_factory)
        for ext in extensions:
            if ext not in self.ext_editor_factories:
                self.ext_editor_factories[ext] = []
            self.ext_editor_factories[ext].append(editor_factory)

    async def on_open(self, event: FileOpenEvent) -> None:
        path = event.path
        extension = Path(path).suffix
        for ext, editor_factories in self.ext_editor_factories.items():
            if ext == extension:
                preferred_editor_factory = editor_factories[0]
                break
        else:
            if None not in self.ext_editor_factories:
                raise RuntimeError(f"Could not find an editor for file extension {extension}")
            preferred_editor_factory = self.ext_editor_factories[None][0]
        editors = self.query("#editor")
        if editors:
            editors.last().remove()
        preferred_editor = preferred_editor_factory()
        self.mount(preferred_editor)
        await preferred_editor.open(path)
        preferred_editor.refresh(layout=True)


class EditorsComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        editors = _Editors()
        ctx.add_resource(editors, name="editors", types=Editors)


c = register_component("editors", EditorsComponent)
