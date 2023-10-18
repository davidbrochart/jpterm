from rich.syntax import Syntax
from textual.document._document import Location
from textual.widgets import TextArea


class TextInput(TextArea):
    def __init__(self, ydoc, ytext, path=None, language=None):
        self.ydoc = ydoc
        self.ytext = ytext
        text = str(ytext)
        if language is None:
            if path is not None:
                language = Syntax.guess_lexer(path, code=text)
        if language == "default":
            language = None
        super().__init__(text, language=language)
        ytext.observe(self.on_change)

    def get_index_from_location(self, location: Location) -> int:
        row, col = location
        index = row * len(self.document.newline) + col
        for i in range(row):
            index += len(self.document.get_line(i))
        return index

    def get_location_from_index(self, index: int) -> Location:
        idx = 0
        newline_len = len(self.document.newline)
        for i in range(self.document.line_count):
            next_idx = idx + len(self.document.get_line(i)) + newline_len
            if index < next_idx:
                return (i, index - idx)
            elif index == next_idx:
                return (i + 1, 0)
            idx = next_idx

    def delete(
        self,
        start,
        end,
        *args,
        **kwargs,
    ):
        top, bottom = sorted((start, end))
        i0 = self.get_index_from_location(top)
        i1 = self.get_index_from_location(bottom)
        with self.ydoc.begin_transaction() as t:
            self.ytext.delete_range(t, i0, i1 - i0)

    def replace(
        self,
        insert,
        start,
        end,
        *args,
        **kwargs,
    ):
        i = self.get_index_from_location(start)
        with self.ydoc.begin_transaction() as t:
            self.ytext.insert(t, i, insert)

    def on_change(self, event):
        insert = None
        delete = None
        retain = None
        for d in event.delta:
            if "insert" in d:
                insert = d["insert"]
            if "delete" in d:
                delete = d["delete"]
            if "retain" in d:
                retain = d["retain"]
        retain = 0 if retain is None else retain
        if insert:
            l0 = self.get_location_from_index(retain)
            super().replace(insert, l0, l0, maintain_selection_offset=False)
        elif delete:
            l1 = self.get_location_from_index(retain)
            l2 = self.get_location_from_index(retain + delete)
            super().delete(l1, l2, maintain_selection_offset=False)
