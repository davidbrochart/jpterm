from functools import partial

import in_n_out as ino
from rich.syntax import Syntax
from rich.traceback import Traceback
from textual.widgets import Static

from txl.base import Contents, Editor, Editors


class TextViewerMeta(type(Editor), type(Static)):
    pass


class TextViewer(Editor, Static, metaclass=TextViewerMeta):

    text: str
    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__(expand=True)
        self.contents = contents

    async def open(self, path: str) -> None:
        self.path = path
        self.ytext = await self.contents.get(path, type="unicode")
        self.text = self.ytext.source
        self.update_viewer()
        self.ytext.observe(self.on_change)

    def update_viewer(self):
        try:
            lexer = Syntax.guess_lexer(self.path, code=self.text)
            syntax = Syntax(
                self.text,
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
            self.sub_title = self.path

    def on_mount(self):
        self.expand

    def on_change(self, target, event):
        self.text = self.ytext.source
        self.update_viewer()


def register_text_viewer(editors: Editors):
    @ino.inject
    def inner(contents: Contents):
        text_viewer_factory = partial(TextViewer, contents)
        editors.register_editor_factory(text_viewer_factory)

    inner()


ino.register_processor(register_text_viewer)
