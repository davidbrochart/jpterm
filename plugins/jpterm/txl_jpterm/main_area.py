from typing import Optional

from textual.app import ComposeResult
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
        self.widget_to_tab = {}
        self.title = 0

    def show(self, widget: Widget, title: Optional[str] = None, mount: bool = True):
        if widget not in self.mounted:
            if title is None:
                title = self.title
                self.title += 1
            tab = Tab(str(title))
            if self.tabs is None:
                self.tabs = Tabs(tab)
            else:
                self.tabs.add_tab(tab)
                self.tabs.active = tab.id
            self.widget_to_tab[widget] = (tab, False)
            self.mounted.append(widget)
            if mount:
                self.mount(widget)
        else:
            tab, dirty = self.widget_to_tab[widget]
            self.tabs.active = tab.id

    def compose(self) -> ComposeResult:
        yield self.tabs
        for widget in self.mounted:
            yield widget

    def get_label(self) -> str:
        tab = self.tabs.active_tab
        return tab.label_text

    def set_label(self, title: str) -> None:
        tab = self.tabs.active_tab
        tab.label = title

    def set_dirty(self, widget: Widget) -> None:
        if widget not in self.mounted:
            return

        tab, dirty = self.widget_to_tab[widget]
        if not dirty:
            self.widget_to_tab[widget] = (tab, True)
            tab.label = "+ " + tab.label_text

    def clear_dirty(self, widget: Widget) -> None:
        if widget not in self.mounted:
            return

        tab, dirty = self.widget_to_tab[widget]
        if dirty:
            self.widget_to_tab[widget] = (tab, False)
            tab.label = tab.label_text[2:]

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        widgets = list(self.widget_to_tab.keys())
        tabs = [tab for tab, dirty in self.widget_to_tab.values()]
        widget = widgets[tabs.index(event.tab)]
        if self.shown is not None:
            self.shown.display = False
        self.shown = widget
        widget.display = True
        widget.focus()
