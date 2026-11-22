from anytext.widgets import Header as AnytextHeader

from txl.base import Header as AbstractHeader


class HeaderMeta(type(AbstractHeader), type(AnytextHeader)):
    pass


class Header(AbstractHeader, AnytextHeader, metaclass=HeaderMeta):
    """Keep the jpterm title local to its view when embedded in a host."""

    @property
    def screen_title(self) -> str:
        return "jpterm"

    @property
    def screen_sub_title(self) -> str:
        return ""
