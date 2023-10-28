import json
import struct
from typing import Any, Dict, List, Optional


def deserialize_msg_from_ws_v1(ws_msg: bytes) -> Dict[str, Any]:
    offset_number = int.from_bytes(ws_msg[:8], "little")
    offsets = [
        int.from_bytes(ws_msg[8 * (i + 1) : 8 * (i + 2)], "little") for i in range(offset_number)
    ]
    channel = ws_msg[offsets[0] : offsets[1]].decode("utf-8")
    msg_list = [ws_msg[offsets[i] : offsets[i + 1]] for i in range(1, offset_number - 1)]
    msg = {
        "channel": channel,
        "header": json.loads(msg_list[0]),
        "parent_header": json.loads(msg_list[1]),
        "metadata": json.loads(msg_list[2]),
        "content": json.loads(msg_list[3]),
    }
    msg["buffers"] = msg_list[4:]
    return msg


def serialize_msg_to_ws_v1(msg: Dict[str, Any]) -> List[bytes]:
    msg_list = [
        json.dumps(msg["header"]).encode("utf-8"),
        json.dumps(msg["parent_header"]).encode("utf-8"),
        json.dumps(msg["metadata"]).encode("utf-8"),
        json.dumps(msg["content"]).encode("utf-8"),
    ] + msg.get("buffers", [])
    channel_b = msg["channel"].encode("utf-8")
    offsets = []
    offsets.append(8 * (1 + 1 + len(msg_list) + 1))
    offsets.append(len(channel_b) + offsets[-1])
    for msg in msg_list:
        offsets.append(len(msg) + offsets[-1])
    offset_number = len(offsets).to_bytes(8, byteorder="little")
    offsets_b = [offset.to_bytes(8, byteorder="little") for offset in offsets]
    bin_msg = [offset_number] + offsets_b + [channel_b] + msg_list
    return b"".join(bin_msg)


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
