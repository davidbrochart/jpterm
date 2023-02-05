import hashlib
import hmac
from typing import Any, Dict, List, Optional, Tuple, cast

from txl_kernel.message import date_to_str, str_to_date
from zmq.utils import jsonapi

DELIM = b"<IDS|MSG>"


def feed_identities(msg_list: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]


def pack(obj: Dict[str, Any]) -> bytes:
    return jsonapi.dumps(obj)


def unpack(s: bytes) -> Dict[str, Any]:
    return cast(Dict[str, Any], jsonapi.loads(s))


def sign(msg_list: List[bytes], key: str) -> bytes:
    auth = hmac.new(key.encode("ascii"), digestmod=hashlib.sha256)
    h = auth.copy()
    for m in msg_list:
        h.update(m)
    return h.hexdigest().encode()


def serialize(
    msg: Dict[str, Any], key: str, change_date_to_str: bool = False
) -> List[bytes]:
    _date_to_str = date_to_str if change_date_to_str else lambda x: x
    message = [
        pack(_date_to_str(msg["header"])),
        pack(_date_to_str(msg["parent_header"])),
        pack(_date_to_str(msg["metadata"])),
        pack(_date_to_str(msg.get("content", {}))),
    ]
    to_send = [DELIM, sign(message, key)] + message + msg.get("buffers", [])
    return to_send


def deserialize(
    msg_list: List[bytes],
    parent_header: Optional[Dict[str, Any]] = None,
    change_str_to_date: bool = False,
) -> Dict[str, Any]:
    _str_to_date = str_to_date if change_str_to_date else lambda x: x
    message: Dict[str, Any] = {}
    header = unpack(msg_list[1])
    message["header"] = _str_to_date(header)
    message["msg_id"] = header["msg_id"]
    message["msg_type"] = header["msg_type"]
    if parent_header:
        message["parent_header"] = parent_header
    else:
        message["parent_header"] = _str_to_date(unpack(msg_list[2]))
    message["metadata"] = unpack(msg_list[3])
    message["content"] = unpack(msg_list[4])
    message["buffers"] = [memoryview(b) for b in msg_list[5:]]
    return message
