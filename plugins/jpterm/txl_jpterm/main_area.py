from textual.widget import Widget
from textual.widgets import Static

from txl.base import MainArea as AbstractMainArea


class MainAreaMeta(type(Widget), type(AbstractMainArea)):
    pass


class MainArea(Widget, AbstractMainArea, metaclass=MainAreaMeta):

    def __init__(self):
        super().__init__(id="main-view")
        self.mounter = None

    def init(self):
        self.mounted = Static()
        super().mount(self.mounted)

    def mount(self, widget):
        if self.mounted:
            self.mounted.remove()
        self.mounted = widget
        super().mount(widget)
