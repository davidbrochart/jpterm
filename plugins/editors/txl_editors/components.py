from pathlib import Path
from typing import Callable, Dict, List

from asphalt.core import Component, Context
from textual.containers import Container
from textual.widgets._header import HeaderTitle
from txl.base import Editor, Editors, FileOpenEvent, Footer, Header
from txl.hooks import register_component


class EditorsMeta(type(Editors), type(Container)):
    pass


class _Editors(Editors, Container, metaclass=EditorsMeta):
    ext_editor_factories: Dict[str, List[Callable[[], Editor]]]

    def __init__(
        self,
        header: Header | None = None,
        footer: Footer | None = None,
    ):
        super().__init__(id="editors")
        self.header = header
        self.footer = footer
        self.ext_editor_factories = {}
        self.editor_factories = []

    def register_editor_factory(self, editor_factory: Callable[[], Editor], extensions: List[str] = [None]):
        self.editor_factories.append(editor_factory)
        for ext in extensions:
            if ext not in self.ext_editor_factories:
                self.ext_editor_factories[ext] = []
            self.ext_editor_factories[ext].append(editor_factory)

    async def on_open(self, event: FileOpenEvent) -> None:
        path = Path(event.path)
        extension = path.suffix
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
        if self.header:
            self.header.query_one(HeaderTitle).text = path.name
        if self.footer:
            bindings = preferred_editor.get_bindings()
            if bindings:
                self.footer.update_bindings(bindings)
        await preferred_editor.open(path)
        preferred_editor.refresh(layout=True)


class EditorsComponent(Component):

    async def start(
        self,
        ctx: Context,
    ) -> None:
        header = await ctx.request_resource(Header, "header")
        footer = await ctx.request_resource(Footer, "footer")
        editors = _Editors(header, footer)
        ctx.add_resource(editors, name="editors", types=Editors)


c = register_component("editors", EditorsComponent)
