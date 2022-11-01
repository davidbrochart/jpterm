from textual.widgets import Header as TextualHeader

from txl.base import Header as AbstractHeader


class HeaderMeta(type(AbstractHeader), type(TextualHeader)):
    pass


class Header(AbstractHeader, TextualHeader, metaclass=HeaderMeta):
    pass
