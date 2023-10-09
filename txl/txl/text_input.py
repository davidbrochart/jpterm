import asyncio

from pycrdt import Text
from rich.syntax import Syntax
from textual.widgets import TextArea


class TextInput(TextArea):
    ytext: Text

    def __init__(self, ytext: Text, path=None, language=None):
        self.ytext = ytext
        text = str(ytext)
        if language is None:
            if path is not None:
                language = Syntax.guess_lexer(path, code=text)
        if language == "default":
            language = None
        super().__init__(text, language=language)
        ytext.observe(self.on_change)
        self.change_events = asyncio.Queue()
        self.observe_changes_task = asyncio.create_task(self.observe_changes())

    def delete(
        self,
        start,
        end,
        *args,
        **kwargs,
    ):
        top, bottom = sorted((start, end))
        i0 = self.document.get_index_from_location(top)
        i1 = self.document.get_index_from_location(bottom)
        del self.ytext[i0:i1]

    def replace(
        self,
        insert,
        start,
        end,
        *args,
        **kwargs,
    ):
        i = self.document.get_index_from_location(start)
        self.ytext[i:i] = insert

    def on_change(self, event):
        self.change_events.put_nowait(event)

    async def observe_changes(self):
        while True:
            event = await self.change_events.get()
            idx = 0
            for d in event.delta:
                retain = d.get("retain")
                if retain is not None:
                    idx += retain
                delete = d.get("delete")
                if delete is not None:
                    l1 = self.document.get_location_from_index(idx)
                    l2 = self.document.get_location_from_index(idx + delete)
                    super().delete(l1, l2, maintain_selection_offset=False)
                insert = d.get("insert")
                if insert is not None:
                    l0 = self.document.get_location_from_index(idx)
                    super().replace(insert, l0, l0, maintain_selection_offset=False)
