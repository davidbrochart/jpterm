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
                self.mount(self.tabs)
            else:
                self.tabs.add_tab(tab)
                self.tabs.active = tab.id
            self.widget_to_tab[widget] = (tab, False)
            self.mounted.append(widget)
            if widget.parent is None:
                self.mount(widget)
        else:
            tab, dirty = self.widget_to_tab[widget]
            self.tabs.active = tab.id

    async def close(self, widget=None):
        widget = self.shown if widget is None else widget
        if widget not in self.widget_to_tab:
            return
        launcher = getattr(self.app, "launcher", None)
        if widget is launcher and len(self.mounted) == 1:
            return
        index = self.mounted.index(widget)
        tab, _ = self.widget_to_tab.pop(widget)
        self.mounted.remove(widget)
        was_shown = self.shown is widget
        if was_shown:
            self.shown = None
        await self.tabs.remove_tab(tab)
        if widget is launcher:
            widget.display = False
        else:
            await widget.remove()
        if was_shown:
            if self.mounted:
                self.show(self.mounted[max(0, index - 1)])
            elif launcher is not None:
                self.show(launcher, "Launcher")

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
        if event.tab not in tabs:
            return
        widget = widgets[tabs.index(event.tab)]
        if self.shown is not None:
            self.shown.display = False
        self.shown = widget
        widget.display = True
        widget.focus()
