from typing import Optional

from textual.widget import Widget
from textual.widgets import Tab, Tabs

from txl.base import MainArea as AbstractMainArea


class MainAreaMeta(type(Widget), type(AbstractMainArea)):
    pass


class MainArea(Widget, AbstractMainArea, metaclass=MainAreaMeta):
    def __init__(self):
        super().__init__(id="main-view")
        self.mounted = []
        self.shown = None
        self.tabs = None
        self.widgets = {}
        self.title = 0

    def show(self, widget: Widget, title: Optional[str] = None):
        if title is None:
            title = self.title
            self.title += 1
        tab = Tab(str(title))
        if self.tabs is None:
            self.tabs = Tabs(tab)
            self.mount(self.tabs)
        else:
            self.tabs.add_tab(tab)
            self.tabs.active = tab.id
        if widget not in self.mounted:
            self.widgets[tab.id] = widget
            self.mounted.append(widget)
            self.mount(widget)

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        widget = self.widgets[event.tab.id]
        if self.shown is not None:
            self.shown.display = False
        self.shown = widget
        widget.display = True
        widget.focus()
