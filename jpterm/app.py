from pathlib import Path
from typing import Any

from rich.console import RenderableType

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App
from textual.widgets import (
    Header,
    Footer,
    FileClick,
    ScrollView,
    DirectoryTree,
    TreeNode,
)
from textual.widgets._directory_tree import DirEntry


class JpDirectoryTree(DirectoryTree):
    def __init__(self, api, path: str, name: str = None) -> None:
        self.api = api
        super().__init__(path, name)

    async def load_directory(self, node: TreeNode[DirEntry]):
        path = node.data.path
        content = await self.api.contents.get_content(path)
        for entry in content:
            await node.add(entry.name, DirEntry(entry.path, entry.is_dir()))
        node.loaded = True
        await node.expand()
        self.refresh(layout=True)


class JptermApp(App):

    api: Any

    async def on_load(self) -> None:
        """Sent before going in to application mode."""

        # Bind our basic keys
        await self.bind("b", "view.toggle('sidebar')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

        # Get path to show
        self.path = "."

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""

        # Create our widgets
        # In this a scroll view for the code and a directory tree
        self.body = ScrollView()
        self.directory = JpDirectoryTree(self.api, self.path, "Code")

        # Dock our widgets
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # Note the directory is also in a scroll view
        await self.view.dock(
            ScrollView(self.directory), edge="left", size=48, name="sidebar"
        )
        await self.view.dock(self.body, edge="top")

    async def handle_file_click(self, message: FileClick) -> None:
        """A message sent by the directory tree when a file is clicked."""

        syntax: RenderableType
        text = await self.api.contents.get_content(message.path)
        lexer = Syntax.guess_lexer(message.path, code=text)
        try:
            syntax = Syntax(
                text,
                lexer,
                line_numbers=True,
                word_wrap=True,
                indent_guides=True,
                theme="monokai",
            )
        except Exception:
            syntax = Traceback(theme="monokai", width=None, show_locals=True)
        self.app.sub_title = Path(message.path).name
        await self.body.update(syntax)
