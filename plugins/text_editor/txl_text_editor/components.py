from asphalt.core import Component, Context
from rich.syntax import Syntax
from rich.traceback import Traceback
from textual.widgets import Static
from txl.base import Editor, Editors, Contents, FileOpenEvent
from txl.hooks import register_component


class TextEditorMeta(type(Editor), type(Static)):
    pass


class TextEditor(Editor, Static, metaclass=TextEditorMeta):

    def __init__(self, contents: Contents) -> None:
        super().__init__(id="editor", expand=True)
        self.contents = contents

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        try:
            code = await self.contents.get_content(path)
            lexer = Syntax.guess_lexer(path, code=code)
            syntax = Syntax(
                code,
                lexer=lexer,
                line_numbers=True,
                word_wrap=False,
                indent_guides=True,
                theme="github-dark",
            )
        except Exception:
            self.update(Traceback(theme="github-dark", width=None))
        else:
            self.update(syntax)
            self.sub_title = path

    def on_mount(self):
        self.expand


class TextEditorComponent(Component):

    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        def text_editor_factory():
            return TextEditor(contents)
        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(text_editor_factory)
        else:
            text_editor = text_editor_factory()
            ctx.add_resource(text_editor, name="text_editor", types=Editor)


c = register_component("text_editor", TextEditorComponent)
