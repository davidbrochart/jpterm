import os
import tempfile

from fps import Module
from PIL import Image
from textual._context import active_app
from textual.app import App
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


class ImageViewerModule(Module):
    def __init__(self, name: str, register: bool = True):
        super().__init__(name)
        self.register = register

    async def start(self) -> None:
        contents = await self.get(Contents)
        app = await self.get(App)

        def image_viewer_factory():
            active_app.set(app)
            return _ImageViewer(contents)

        if self.register:
            editors = await self.get(Editors)
            editors.register_editor_factory(image_viewer_factory, [".png", ".jpg", ".jpeg"])
        else:
            image_viewer = image_viewer_factory()
            self.put(image_viewer, Editor)
