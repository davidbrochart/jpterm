from rich.console import RenderableType
from rich.style import StyleType
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Event
from textual.geometry import Region
from textual.keys import Keys
from textual.widget import Widget
from textual.widgets import Static


class TextInput(Static, can_focus=True):
    def __init__(
        self,
        ydoc,
        ytext,
        lexer: str,
        style: StyleType = "gold1 on grey11",
        syntax_theme: str = "ansi_dark",
        show_cursor: bool = False,
        parent_widget: Widget = None,
        scrollable_widget: VerticalScroll = None,
    ) -> None:
        super().__init__()
        self.ydoc = ydoc
        self.ytext = ytext
        self.lines = str(ytext).splitlines()
        self._row = 0
        self._col = 0
        self._pos = 0
        self.style = style
        self.syntax = Syntax("", lexer, theme=syntax_theme, word_wrap=True)
        self.show_cursor = show_cursor
        self.parent_widget = parent_widget
        self.scrollable_widget = scrollable_widget
        self.clicked = False

    def set_pos(self):
        pos = 0
        for row in range(self._row):
            pos += len(self.lines[row]) + 1
        pos += self._col
        self._pos = pos

    @property
    def row(self) -> int:
        return self._row

    @row.setter
    def row(self, value: int) -> None:
        self._row = value

    @property
    def col(self) -> int:
        return self._col

    @col.setter
    def col(self, value: int) -> None:
        self._col = value

    def highlight(self, code: str, start: str = "", end: str = "") -> Text:
        text = self.syntax.highlight(code)
        if not code.endswith("\n"):
            text = text[:-1]
        return Text(start) + text + Text(end)

    def render(self) -> RenderableType:
        text = Text()

        if not self.show_cursor:
            text += self.highlight("\n".join(self.lines), end="\n")
            return text

        if self.row > 0:
            # text above prompt
            text += self.highlight("\n".join(self.lines[: self.row]), end="\n")

        # prompt
        if self.col == len(self.lines[self.row]):
            # cursor at EOL, add an extra space
            end = " "
        else:
            end = ""
        prompt = self.highlight(self.lines[self.row], end=end)
        prompt.stylize("reverse", self.col, self.col + 1)
        text += prompt

        if self.row < len(self.lines) - 1:
            # text below prompt
            text += self.highlight(
                "\n".join(self.lines[self.row + 1 :]), start="\n", end=""
            )

        return text

    def on_focus(self):
        self.show_cursor = True
        self.update()

    def on_blur(self):
        self.show_cursor = False
        self.update()

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.Escape:
            self.blur()
            if self.parent_widget is not None:
                self.parent_widget.focus()
        elif event.key == Keys.Up:
            if self.row > 0:
                self.row -= 1
                self.col = min(len(self.lines[self.row]), self.col)
                self.set_pos()
                if self.scrollable_widget is not None:
                    self.scrollable_widget.scroll_to_region(
                        Region(x=self.col, y=self.row, width=1, height=1)
                    )
        elif event.key == Keys.Down:
            if self.row < len(self.lines) - 1:
                self.row += 1
                self.col = min(len(self.lines[self.row]), self.col)
                self.set_pos()
                if self.scrollable_widget is not None:
                    self.scrollable_widget.scroll_to_region(
                        Region(x=self.col, y=self.row, width=1, height=1)
                    )
        elif event.key == Keys.Return or event.key == Keys.Enter:
            with self.ydoc.begin_transaction() as t:
                self.ytext.insert(t, self._pos, "\n")
            self.lines.insert(self.row, self.lines[self.row][: self.col])
            self.row += 1
            self.lines[self.row] = self.lines[self.row][self.col :]
            self.col = 0
            self.set_pos()
        elif event.key == Keys.Home:
            self.col = 0
            self.set_pos()
        elif event.key == Keys.End:
            self.col = len(self.lines[self.row])
            self.set_pos()
        elif event.key in [Keys.Backspace, "ctrl+h"]:
            if self.col == 0:
                if self.row != 0:
                    with self.ydoc.begin_transaction() as t:
                        self.ytext.delete(t, self._pos - 1)
                    self.row -= 1
                    self.col = len(self.lines[self.row])
                    self.lines[self.row] += self.lines[self.row + 1]
                    del self.lines[self.row + 1]
                    self.set_pos()
            else:
                with self.ydoc.begin_transaction() as t:
                    self.ytext.delete(t, self._pos - 1)
                self.lines[self.row] = (
                    self.lines[self.row][: self.col - 1]
                    + self.lines[self.row][self.col :]
                )
                self.col -= 1
                self.set_pos()
        elif event.key == Keys.Delete:
            if self.col == len(self.lines[self.row]):
                if self.row < len(self.lines) - 1:
                    with self.ydoc.begin_transaction() as t:
                        self.ytext.delete(t, self._pos)
                    self.lines[self.row] += self.lines[self.row + 1]
                    del self.lines[self.row + 1]
                    self.set_pos()
            else:
                with self.ydoc.begin_transaction() as t:
                    self.ytext.delete(t, self._pos)
                self.lines[self.row] = (
                    self.lines[self.row][: self.col]
                    + self.lines[self.row][self.col + 1 :]
                )
                self.set_pos()
        elif event.key == Keys.Left:
            if self.col == 0:
                if self.row != 0:
                    self.row -= 1
                    self.col = len(self.lines[self.row])
                    self.set_pos()
            else:
                self.col -= 1
                self.set_pos()
        elif event.key == Keys.Right:
            if self.col == len(self.lines[self.row]):
                if self.row < len(self.lines) - 1:
                    self.row += 1
                    self.col = 0
                    self.set_pos()
            else:
                self.col += 1
                self.set_pos()
        elif event.is_printable or event.key == Keys.Space:
            if event.key == Keys.Space:
                key = " "
            else:
                key = event.character
            with self.ydoc.begin_transaction() as t:
                self.ytext.insert(t, self._pos, key)
            self.lines[self.row] = (
                self.lines[self.row][: self.col]
                + key
                + self.lines[self.row][self.col :]
            )
            self.col += 1
            self.set_pos()

        event.stop()
        self.update()

    def on_click(self) -> None:
        self.clicked = True
        self.focus()
        self.show_cursor = True
        self.update()


class ScrollableTextInput(VerticalScroll):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.viewer = TextInput(scrollable_widget=self, *args, **kwargs)

    def compose(self) -> ComposeResult:
        yield self.viewer
