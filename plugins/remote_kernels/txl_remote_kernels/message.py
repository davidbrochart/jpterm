import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dateutil.parser import parse as dateutil_parse

protocol_version_info = (5, 3)
protocol_version = "%i.%i" % protocol_version_info


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


def serialize(msg: Dict[str, Any]) -> List[bytes]:
    # TODO: buffers
    nbufs = int(1).to_bytes(4, "big")
    offset_0 = int(8).to_bytes(4, "big")
    message = nbufs + offset_0 + json.dumps(msg).encode("utf8")
    return message


def deserialize(
    msg: bytes,
) -> Dict[str, Any]:
    # TODO: buffers
    # nbufs = int.from_bytes(msg[:4], byteorder="little")
    offset_0 = int.from_bytes(msg[4:8], byteorder="little")
    message = json.loads(msg[offset_0:])
    return message


async def send_message(
    message, channel: str, websocket, change_date_to_str: bool = False
):
    _date_to_str = date_to_str if change_date_to_str else lambda x: x
    message["header"] = _date_to_str(message["header"])
    message["parent_header"] = _date_to_str(message["parent_header"])
    message["metadata"] = _date_to_str(message["metadata"])
    message["content"] = _date_to_str(message.get("content", {}))
    message["channel"] = channel
    # msg = serialize(message)
    # await websocket.send_bytes(msg)
    await websocket.send_json(message)


async def receive_message(
    websocket, timeout: float, change_str_to_date: bool = False
) -> Optional[Dict[str, Any]]:
    try:
        message = await websocket.receive_json(timeout)
    except asyncio.TimeoutError:
        return None
    _str_to_date = str_to_date if change_str_to_date else lambda x: x
    message["header"] = _str_to_date(message["header"])
    message["parent_header"] = _str_to_date(message["parent_header"])
    # return deserialize(message, change_str_to_date)
