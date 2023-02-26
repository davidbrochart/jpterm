import os
import tempfile
from functools import partial

import in_n_out as ino
from PIL import Image
from textual.widget import Widget
from textual_imageview.viewer import ImageViewer

from txl.base import Contents, Editor, Editors


class ImageViewerMeta(type(Editor), type(Widget)):
    pass


class _ImageViewer(Editor, Widget, metaclass=ImageViewerMeta):

    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__()
        self.contents = contents
        self.image_viewer = None

    async def open(self, path: str) -> None:
        self.ydoc = await self.contents.get(path, type="blob")
        self.data = self.ydoc.source
        self.update_viewer()
        self.ydoc.observe(self.on_change)

    def update_viewer(self):
        if not self.data:
            return
        f = tempfile.NamedTemporaryFile(delete=False)
        try:
            f.write(self.data)
            f.close()
        finally:
            image = Image.open(f.name)
            os.unlink(f.name)
        if self.image_viewer:
            self.image_viewer.remove()
        self.image_viewer = ImageViewer(image)
        self.mount(self.image_viewer)

    def on_change(self, target, event):
        self.data = self.ydoc.source
        self.update_viewer()


def register_image_viewer(editors: Editors):
    @ino.inject
    def inner(contents: Contents):
        image_viewer_factory = partial(_ImageViewer, contents)
        editors.register_editor_factory(image_viewer_factory, [".png", ".jpg", ".jpeg"])

    inner()


ino.register_processor(register_image_viewer)
