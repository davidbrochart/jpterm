import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast
from uuid import uuid4

from dateutil.parser import parse as dateutil_parse  # type: ignore
from zmq.asyncio import Socket
from zmq.utils import jsonapi

protocol_version_info = (5, 3)
protocol_version = "%i.%i" % protocol_version_info

DELIM = b"<IDS|MSG>"


def feed_identities(msg_list: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]  # noqa


def str_to_date(obj: Dict[str, Any]) -> Dict[str, Any]:
    if "date" in obj:
        obj["date"] = dateutil_parse(obj["date"])
    return obj


def date_to_str(obj: Dict[str, Any]):
    if "date" in obj and type(obj["date"]) is not str:
        obj["date"] = obj["date"].isoformat().replace("+00:00", "Z")
    return obj


def utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def create_message_header(
    msg_type: str, session_id: str, msg_id: str
) -> Dict[str, Any]:
    if not session_id:
        session_id = msg_id = uuid4().hex
    else:
        msg_id = f"{session_id}_{msg_id}"
    header = {
        "date": utcnow().isoformat().replace("+00:00", "Z"),
        "msg_id": msg_id,
        "msg_type": msg_type,
        "session": session_id,
        "username": "",
        "version": protocol_version,
    }
    return header


def create_message(
    msg_type: str,
    content: Dict = {},
    session_id: str = "",
    msg_id: str = "",
) -> Dict[str, Any]:
    header = create_message_header(msg_type, session_id, msg_id)
    msg = {
        "header": header,
        "msg_id": header["msg_id"],
        "msg_type": header["msg_type"],
        "parent_header": {},
        "content": content,
        "metadata": {},
        "buffers": [],
    }
    return msg


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


async def send_message(
    msg: Dict[str, Any], sock: Socket, key: str, change_date_to_str: bool = False
) -> None:
    await sock.send_multipart(
        serialize(msg, key, change_date_to_str=change_date_to_str), copy=True
    )


async def receive_message(
    sock: Socket, timeout: float = float("inf"), change_str_to_date: bool = False
) -> Optional[Dict[str, Any]]:
    timeout *= 1000  # in ms
    ready = await sock.poll(timeout)
    if ready:
        msg_list = await sock.recv_multipart()
        idents, msg_list = feed_identities(msg_list)
        return deserialize(msg_list, change_str_to_date=change_str_to_date)
    return None
