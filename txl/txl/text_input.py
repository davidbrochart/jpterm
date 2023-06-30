from rich.console import RenderableType
from rich.style import StyleType
from rich.syntax import Syntax
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
        text = str(ytext)
        if text[-1] != "\n":
            with self.ydoc.begin_transaction() as t:
                self.ytext.extend(t, "\n")
        self.row = 0
        self.col = 0
        self.pos = 0
        self.style = style
        self.syntax = Syntax("", lexer, theme=syntax_theme, word_wrap=True)
        self.show_cursor = show_cursor
        self.parent_widget = parent_widget
        self.scrollable_widget = scrollable_widget
        self.clicked = False
        ytext.observe(self.on_change)

    def set_pos(self, row, col, lines):
        pos = 0
        for i in range(row):
            pos += len(lines[i]) + 1
        pos += col
        self.pos = pos

    def get_row_col_lines(self):
        lines = str(self.ytext).splitlines()
        row = 0
        col = self.pos
        while True:
            line_len = len(lines[row])
            if col <= line_len:
                break
            row += 1
            col -= line_len + 1
        return row, col, lines

    def render(self) -> RenderableType:
        rendered = self.syntax.highlight(str(self.ytext))

        if self.show_cursor:
            if str(rendered[self.pos]) == "\n":
                rendered = rendered[: self.pos] + " " + rendered[self.pos :]
            rendered.stylize("reverse", self.pos, self.pos + 1)

        return rendered

    def on_focus(self):
        self.show_cursor = True
        self.update()

    def on_blur(self):
        self.show_cursor = False
        self.update()

    def on_change(self, event):
        insert = None
        delete = None
        retain = None
        for d in event.delta:
            if "insert" in d:
                insert = d["insert"]
            elif "delete" in d:
                delete = d["delete"]
            elif "retain" in d:
                retain = d["retain"]
        i = 0 if retain is None else retain
        if insert is not None:
            if i <= self.pos:
                self.pos += 1
            self.update()
        if delete is not None:
            if i == len(self.ytext):
                # FIXME: launch in a task
                with self.ydoc.begin_transaction() as t:
                    self.ytext.extend(t, "\n")
            elif i < self.pos:
                self.pos -= 1
            self.update()

    async def on_key(self, event: Event) -> None:
        if event.key == Keys.Escape:
            self.blur()
            if self.parent_widget is not None:
                self.parent_widget.focus()
            event.stop()
        elif event.key == Keys.Up:
            row, col, lines = self.get_row_col_lines()
            if row > 0:
                row -= 1
                col = min(len(lines[row]), col)
                self.set_pos(row, col, lines)
                if self.scrollable_widget is not None:
                    self.scrollable_widget.scroll_to_region(
                        Region(x=col, y=row, width=1, height=1)
                    )
                self.update()
            event.stop()
        elif event.key == Keys.Down:
            row, col, lines = self.get_row_col_lines()
            if row < len(lines) - 1:
                row += 1
                col = min(len(lines[row]), col)
                self.set_pos(row, col, lines)
                if self.scrollable_widget is not None:
                    self.scrollable_widget.scroll_to_region(
                        Region(x=col, y=row, width=1, height=1)
                    )
                self.update()
            event.stop()
        elif event.key == Keys.Return or event.key == Keys.Enter:
            with self.ydoc.begin_transaction() as t:
                self.ytext.insert(t, self.pos, "\n")
            event.stop()
        elif event.key == Keys.Home:
            row, col, lines = self.get_row_col_lines()
            col = 0
            self.set_pos(row, col, lines)
            self.update()
            event.stop()
        elif event.key == Keys.End:
            row, col, lines = self.get_row_col_lines()
            col = len(lines[row])
            self.set_pos(row, col, lines)
            self.update()
            event.stop()
        elif event.key in [Keys.Backspace, Keys.ControlH]:
            if self.pos > 0:
                with self.ydoc.begin_transaction() as t:
                    self.ytext.delete(t, self.pos - 1)
            event.stop()
        elif event.key == Keys.Delete:
            if self.pos < len(self.ytext) - 2:
                with self.ydoc.begin_transaction() as t:
                    self.ytext.delete(t, self.pos)
            event.stop()
        elif event.key == Keys.Left:
            if self.pos > 0:
                self.pos -= 1
                self.update()
            event.stop()
        elif event.key == Keys.Right:
            if self.pos < len(self.ytext) - 1:
                self.pos += 1
                self.update()
            event.stop()
        elif event.is_printable:
            key = event.character
            with self.ydoc.begin_transaction() as t:
                self.ytext.insert(t, self.pos, key)
            event.stop()

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
