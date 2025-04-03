from fps import Module
from textual._context import active_app
from textual.app import App
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
        app: App,
        main_area: MainArea,
    ):
        super().__init__()
        self._app = app
        self.main_area = main_area
        self.documents = {}
        self.buttons = []
        self._initialized = False

    def register(self, id_: str, document):
        active_app.set(self._app)
        self.documents[id_] = document
        button = Button(id_, id=id_)
        if self._initialized:
            self.mount(button)
        else:
            self.buttons.append(button)

    def compose(self):
        self._initialized = True
        return self.buttons

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        document = self.documents[event.button.id]()
        self.main_area.show(document)
        await document.open()


class LauncherModule(Module):
    async def start(self) -> None:
        app = await self.get(App)
        main_area = await self.get(MainArea)
        launcher = _Launcher(app, main_area)
        self.put(launcher, Launcher)
