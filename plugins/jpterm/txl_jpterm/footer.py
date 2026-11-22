from __future__ import annotations

from anytext.widgets import Footer as AnytextFooter
from anytext.widgets._footer import FooterKey

from txl.base import Footer as AbstractFooter


class FooterMeta(type(AbstractFooter), type(AnytextFooter)):
    pass


class Footer(AbstractFooter, AnytextFooter, metaclass=FooterMeta):
    """Show shortcuts belonging to this jpterm view, excluding host bindings."""

    def compose(self):
        view = self.parent
        allowed = {
            key
            for key, active in self.screen.active_bindings.items()
            if active[0] is view or (view is not None and view in active[0].ancestors)
        }
        for widget in super().compose():
            if not isinstance(widget, FooterKey) or widget.key in allowed:
                yield widget
