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
        if widget not in self.mounted:
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
            self.widgets[tab] = widget
            self.mounted.append(widget)
            self.mount(widget)
        else:
            tab = list(self.widgets.keys())[list(self.widgets.values()).index(widget)]
            self.tabs.active = tab.id

    def get_label(self) -> str:
        tab = self.tabs.active_tab
        return tab.label_text

    def set_label(self, title: str) -> None:
        tab = self.tabs.active_tab
        tab.label = title

    def set_dirty(self, widget: Widget) -> None:
        if widget not in self.mounted:
            return

        tab = list(self.widgets.keys())[list(self.widgets.values()).index(widget)]
        if not tab.label_text.startswith("+ "):
            tab.label = "+ " + tab.label_text

    def clear_dirty(self, widget: Widget) -> None:
        if widget not in self.mounted:
            return

        tab = list(self.widgets.keys())[list(self.widgets.values()).index(widget)]
        if tab.label_text.startswith("+ "):
            tab.label = tab.label_text[2:]

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        widget = self.widgets[event.tab]
        if self.shown is not None:
            self.shown.display = False
        self.shown = widget
        widget.display = True
        widget.focus()
