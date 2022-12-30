import os
import tempfile

from asphalt.core import Component, Context
from PIL import Image
from textual.widget import Widget
from textual_imageview.viewer import ImageViewer

from txl.base import Contents, Editor, Editors, FileOpenEvent
from txl.hooks import register_component


class ImageViewerMeta(type(Editor), type(Widget)):
    pass


class _ImageViewer(Editor, Widget, metaclass=ImageViewerMeta):

    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__()
        self.contents = contents
        self.image_viewer = None

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

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


class ImageViewerComponent(Component):
    def __init__(self, register: bool = True):
        super().__init__()
        self.register = register

    async def start(
        self,
        ctx: Context,
    ) -> None:
        contents = await ctx.request_resource(Contents, "contents")

        def image_viewer_factory():
            return _ImageViewer(contents)

        if self.register:
            editors = await ctx.request_resource(Editors, "editors")
            editors.register_editor_factory(
                image_viewer_factory, [".png", ".jpg", ".jpeg"]
            )
        else:
            image_viewer = image_viewer_factory()
            ctx.add_resource(image_viewer, name="image_viewer", types=Editor)


c = register_component("image_viewer", ImageViewerComponent)
