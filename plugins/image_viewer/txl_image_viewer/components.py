import os
import tempfile

from asphalt.core import Component, Context
from PIL import Image
from textual_imageview.viewer import ImageViewer
from textual.widget import Widget
from txl.base import Editor, Editors, Contents, FileOpenEvent
from txl.hooks import register_component


class ImageViewerMeta(type(Editor), type(Widget)):
    pass


class _ImageViewer(Editor, Widget, metaclass=ImageViewerMeta):

    contents: Contents
    path: str

    def __init__(self, contents: Contents) -> None:
        super().__init__()
        self.contents = contents

    async def on_open(self, event: FileOpenEvent) -> None:
        await self.open(event.path)

    async def open(self, path: str) -> None:
        data = await self.contents.get(path, type="bytes", on_change=self.on_change)
        f = tempfile.NamedTemporaryFile(delete=False)
        try:
            f.write(data)
            f.close()
        finally:
            image = Image.open(f.name)
            os.unlink(f.name)
        image_viewer = ImageViewer(image)
        self.mount(image_viewer)

    def on_change(self, value):
        pass


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
            editors.register_editor_factory(image_viewer_factory, [".png"])
        else:
            image_viewer = image_viewer_factory()
            ctx.add_resource(image_viewer, name="image_viewer", types=Editor)


c = register_component("image_viewer", ImageViewerComponent)
