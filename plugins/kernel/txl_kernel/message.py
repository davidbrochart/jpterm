from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from dateutil.parser import parse as dateutil_parse

PROTOCOL_VERSION = "5.3"


def utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def date_to_str(obj: Dict[str, Any]):
    if "date" in obj and type(obj["date"]) is not str:
        obj["date"] = obj["date"].isoformat().replace("+00:00", "Z")
    return obj


def str_to_date(obj: Dict[str, Any]) -> Dict[str, Any]:
    if "date" in obj:
        obj["date"] = dateutil_parse(obj["date"])
    return obj


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
        "version": PROTOCOL_VERSION,
    }
    return header


def create_message(
    msg_type: str,
    content: Dict = {},
    session_id: str = "",
    msg_id: str = "",
    buffers: List = [],
) -> Dict[str, Any]:
    header = create_message_header(msg_type, session_id, msg_id)
    msg = {
        "header": header,
        "msg_id": header["msg_id"],
        "msg_type": header["msg_type"],
        "parent_header": {},
        "content": content,
        "metadata": {},
        "buffers": buffers,
    }
    return msg
