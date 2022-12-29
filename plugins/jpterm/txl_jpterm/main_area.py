from textual.widget import Widget

from txl.base import MainArea as AbstractMainArea


class MainAreaMeta(type(Widget), type(AbstractMainArea)):
    pass


class MainArea(Widget, AbstractMainArea, metaclass=MainAreaMeta):
    def __init__(self):
        super().__init__(id="main-view")
        self.mounted = []
        self.shown = None

    def show(self, widget):
        if self.shown:
            self.shown.display = False
        self.shown = widget
        if widget in self.mounted:
            widget.display = True
        else:
            self.mount(widget)
            self.mounted.append(widget)
