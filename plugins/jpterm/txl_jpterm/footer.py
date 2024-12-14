from __future__ import annotations

from textual.widgets import Footer as TextualFooter

from txl.base import Footer as AbstractFooter


class FooterMeta(type(AbstractFooter), type(TextualFooter)):
    pass


class Footer(AbstractFooter, TextualFooter, metaclass=FooterMeta):
    pass
