from __future__ import annotations

import os.path
from dataclasses import dataclass
from typing import ClassVar

from asphalt.core import Component, Context
from rich.style import Style
from rich.text import Text, TextType
from textual._types import MessageTarget
from textual.message import Message
from textual.widgets._tree import TOGGLE_STYLE, Tree, TreeNode

from txl.base import Contents, FileBrowser
from txl.hooks import register_component


@dataclass
class DirEntry:
    path: str
    is_dir: bool
    loaded: bool = False


class DirectoryTreeMeta(type(FileBrowser), type(Tree)):
    pass


class DirectoryTree(FileBrowser, Tree[DirEntry], metaclass=DirectoryTreeMeta):
    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "tree--label",
        "tree--guides",
        "tree--guides-hover",
        "tree--guides-selected",
        "tree--cursor",
        "tree--highlight",
        "tree--highlight-line",
        "directory-tree--folder",
        "directory-tree--file",
        "directory-tree--extension",
        "directory-tree--hidden",
    }

    DEFAULT_CSS = """
    DirectoryTree > .directory-tree--folder {
        text-style: bold;
    }
    DirectoryTree > .directory-tree--file {

    }
    DirectoryTree > .directory-tree--extension {
        text-style: italic;
    }
    DirectoryTree > .directory-tree--hidden {
        color: $text 50%;
    }
    """

    class FileSelected(Message, bubble=True):
        def __init__(self, sender: MessageTarget, path: str) -> None:
            self.path = path
            super().__init__(sender)

    def __init__(
        self,
        path: str,
        contents: Contents,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.path = os.path.expanduser(path.rstrip("/"))
        name = os.path.basename(self.path)
        self.contents = contents
        super().__init__(
            self.path, data=DirEntry(self.path, True), name=name, id=id, classes=classes
        )

    def process_label(self, label: TextType):
        """Process a str or Text in to a label. Maybe overridden in a subclass to change
        modify how labels are rendered.
        Args:
            label (TextType): Label.
        Returns:
            Text: A Rich Text object.
        """
        if isinstance(label, str):
            text_label = Text(label)
        else:
            text_label = label
        first_line = text_label.split()[0]
        return first_line

    def render_label(self, node: TreeNode[DirEntry], base_style: Style, style: Style):
        node_label = node._label.copy()
        node_label.stylize(style)

        if node._allow_expand:
            prefix = ("📂 " if node.is_expanded else "📁 ", base_style + TOGGLE_STYLE)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            prefix = (
                "📄 ",
                base_style,
            )
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True),
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden")
            )

        text = Text.assemble(prefix, node_label)
        return text

    async def load_directory(self, node: TreeNode[DirEntry]) -> None:
        assert node.data is not None
        dir_path = node.data.path
        node.data.loaded = True
        directory = await self.contents.get(dir_path, is_dir=True)
        for path in directory:
            node.add(
                path.name,
                data=DirEntry(str(path.path), path.is_dir()),
                allow_expand=path.is_dir(),
            )
        node.expand()

    def on_mount(self) -> None:
        self.call_later(self.load_directory, self.root)

    async def on_tree_node_expanded(self, event: Tree.NodeSelected) -> None:
        event.stop()
        dir_entry = event.node.data
        if dir_entry is None:
            return
        if dir_entry.is_dir:
            if not dir_entry.loaded:
                await self.load_directory(event.node)
        else:
            self.open_file_signal.dispatch(dir_entry.path)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()
        dir_entry = event.node.data
        if dir_entry is None:
            return
        if not dir_entry.is_dir:
            self.open_file_signal.dispatch(dir_entry.path)


class FileBrowserComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")
        file_browser = DirectoryTree(".", contents, id="browser-view")
        ctx.add_resource(file_browser, name="file_browser", types=FileBrowser)


c = register_component("file_browser", FileBrowserComponent)
