from asphalt.core import Component, Context
from textual.widget import Widget
from textual.widgets import Button

from txl.base import Launcher, MainArea


class LauncherMeta(type(Launcher), type(Widget)):
    pass


class _Launcher(Launcher, Widget, metaclass=LauncherMeta):
    DEFAULT_CSS = """
    _Launcher {
        padding: 1;
    }
    """

    def __init__(
        self,
        main_area: MainArea,
    ):
        super().__init__()
        self.main_area = main_area
        self.documents = {}
        self.buttons = []

    def register(self, id_: str, document):
        self.documents[id_] = document
        button = Button(id_, id=id_)
        self.buttons.append(button)

    def compose(self):
        return self.buttons

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        document = self.documents[event.button.id]()
        self.main_area.show(document)
        await document.open()


class LauncherComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        main_area = await ctx.request_resource(MainArea)
        launcher = _Launcher(main_area)
        ctx.add_resource(launcher, types=Launcher)
