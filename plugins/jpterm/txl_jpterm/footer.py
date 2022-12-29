from __future__ import annotations

from collections import defaultdict

import rich.repr
from rich.console import RenderableType
from rich.text import Text
from textual import events
from textual.reactive import Reactive, watch
from textual.widget import Widget

from txl.base import Footer as AbstractFooter


class FooterMeta(type(AbstractFooter), type(Widget)):
    pass


@rich.repr.auto
class Footer(AbstractFooter, Widget, metaclass=FooterMeta):
    """A simple header widget which docks itself to the top of the parent container."""

    DEFAULT_CSS = """
    Footer {
        background: $accent;
        color: $text;
        dock: bottom;
        height: 1;
    }
    Footer > .footer--highlight {
        background: $accent-darken-1;
    }

    Footer > .footer--highlight-key {
        background: $secondary;
        text-style: bold;
    }

    Footer > .footer--key {
        text-style: bold;
        background: $accent-darken-2;
    }
    """

    COMPONENT_CLASSES = {
        "footer--description",
        "footer--key",
        "footer--highlight",
        "footer--highlight-key",
    }

    def __init__(self) -> None:
        super().__init__()
        self._key_text: Text | None = None
        self._bindings = None
        self.auto_links = False

    highlight_key: Reactive[str | None] = Reactive(None)

    async def watch_highlight_key(self, value) -> None:
        """If highlight key changes we need to regenerate the text."""
        self._key_text = None

    def on_mount(self) -> None:
        watch(self.screen, "focused", self._focus_changed)

    def _focus_changed(self, focused: Widget | None) -> None:
        self._key_text = None
        self.refresh()

    async def on_mouse_move(self, event: events.MouseMove) -> None:
        """Store any key we are moving over."""
        self.highlight_key = event.style.meta.get("key")

    async def on_leave(self, event: events.Leave) -> None:
        """Clear any highlight when the mouse leaves the widget"""
        self.highlight_key = None

    def __rich_repr__(self) -> rich.repr.Result:
        yield from super().__rich_repr__()

    def make_key_text(self) -> Text:
        """Create text containing all the keys."""
        bindings = self._bindings
        base_style = self.rich_style
        text = Text(
            style=self.rich_style,
            no_wrap=True,
            overflow="ellipsis",
            justify="left",
            end="",
        )
        highlight_style = self.get_component_rich_style("footer--highlight")
        highlight_key_style = self.get_component_rich_style("footer--highlight-key")
        key_style = self.get_component_rich_style("footer--key")

        if bindings is None:
            bindings = [
                binding
                for (_namespace, binding) in self.app.namespace_bindings.values()
                if binding.show
            ]

        action_to_bindings = defaultdict(list)
        for binding in bindings:
            action_to_bindings[binding.action].append(binding)

        for action, bindings in action_to_bindings.items():
            binding = bindings[0]
            key_display = (
                binding.key.upper()
                if binding.key_display is None
                else binding.key_display
            )
            hovered = self.highlight_key == binding.key
            key_text = Text.assemble(
                (f" {key_display} ", highlight_key_style if hovered else key_style),
                (
                    f" {binding.description} ",
                    highlight_style if hovered else base_style,
                ),
                meta={
                    "@click": f"app.check_bindings('{binding.key}')"
                    if self._bindings is None
                    else binding.action,
                    "key": binding.key,
                },
            )
            text.append_text(key_text)
        return text

    def post_render(self, renderable):
        return renderable

    def render(self) -> RenderableType:
        if self._key_text is None:
            self._key_text = self.make_key_text()
        return self._key_text
