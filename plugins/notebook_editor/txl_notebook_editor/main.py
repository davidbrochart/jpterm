from functools import partial
from typing import Type

import in_n_out as ino
from textual.containers import Container

from txl.base import CellFactory, Contents, Editor, Editors, Kernels


class NotebookEditorMeta(type(Editor), type(Container)):
    pass


class NotebookEditor(Editor, Container, metaclass=NotebookEditorMeta):
    def __init__(
        self,
        contents: Contents,
        kernels: Type[Kernels],
        cell_factory: CellFactory,
    ) -> None:
        super().__init__()
        self.contents = contents
        self.kernels = kernels
        self.cell_factory = cell_factory
        self.kernel = None

    async def open(self, path: str) -> None:
        self.ynb = await self.contents.get(path, type="notebook")
        ipynb = self.ynb.source
        self.language = (
            ipynb.get("metadata", {}).get("kernelspec", {}).get("language", "")
        )
        kernel_name = ipynb.get("metadata", {}).get("kernelspec", {}).get("name")
        if kernel_name:
            self.kernel = self.kernels(kernel_name)
        self.update()

    def update(self):
        for i_cell in range(self.ynb.cell_number):
            cell = self.cell_factory(
                self.ynb._ycells[i_cell], self.ynb.ydoc, self.language, self.kernel
            )
            self.mount(cell)


def register_notebook_editor(editors: Editors):
    @ino.inject
    def inner(contents: Contents, kernels: Type[Kernels], cell_factory: CellFactory):
        notebook_editor_factory = partial(
            NotebookEditor, contents, kernels, cell_factory
        )
        editors.register_editor_factory(notebook_editor_factory, [".ipynb"])

    inner()


ino.register_processor(register_notebook_editor)
