from typing import TypeVar

from anyio.streams.stapled import StapledObjectStream as _StapledObjectStream

T_Item = TypeVar("T_Item")


# FIXME: remove when https://github.com/agronholm/anyio/pull/1241 is released
class StapledObjectStream(_StapledObjectStream[T_Item]):
    def send_nowait(self, item: T_Item) -> None:
        self.send_stream.send_nowait(item)  # type: ignore[attr-defined]
