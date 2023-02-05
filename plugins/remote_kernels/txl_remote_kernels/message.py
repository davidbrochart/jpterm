import json
import struct
from typing import Any, Dict, Optional


def to_binary(msg: Dict[str, Any]) -> Optional[bytes]:
    if not msg["buffers"]:
        return None
    buffers = msg.pop("buffers")
    bmsg = json.dumps(msg).encode("utf8")
    buffers.insert(0, bmsg)
    n = len(buffers)
    offsets = [4 * (n + 1)]
    for b in buffers[:-1]:
        offsets.append(offsets[-1] + len(b))
    header = struct.pack("!" + "I" * (n + 1), n, *offsets)
    buffers.insert(0, header)
    return b"".join(buffers)


def from_binary(bmsg: bytes) -> Dict[str, Any]:
    n = struct.unpack("!i", bmsg[:4])[0]
    offsets = list(struct.unpack("!" + "I" * n, bmsg[4 : 4 * (n + 1)]))  # noqa
    offsets.append(None)
    buffers = []
    for start, stop in zip(offsets[:-1], offsets[1:]):
        buffers.append(bmsg[start:stop])
    msg = json.loads(buffers[0].decode("utf8"))
    msg["buffers"] = buffers[1:]
    return msg
