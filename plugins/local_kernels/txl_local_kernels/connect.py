import asyncio
import json
import os
import socket
import tempfile
import uuid
from typing import Dict, Optional, Tuple, Union

import zmq
import zmq.asyncio
from zmq.asyncio import Socket

channel_socket_types = {
    "hb": zmq.REQ,
    "shell": zmq.DEALER,
    "iopub": zmq.SUB,
    "stdin": zmq.DEALER,
    "control": zmq.DEALER,
}

context = zmq.asyncio.Context()

cfg_t = Dict[str, Union[str, int]]


def get_port(ip: str) -> int:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\0" * 8)
    sock.bind((ip, 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def write_connection_file(
    fname: str = "",
    ip: str = "",
    transport: str = "tcp",
    signature_scheme: str = "hmac-sha256",
    kernel_name: str = "",
) -> Tuple[str, cfg_t]:
    ip = ip or "127.0.0.1"

    if not fname:
        fd, fname = tempfile.mkstemp(suffix=".json")
        os.close(fd)
    f = open(fname, "wt")

    channels = ["shell", "iopub", "stdin", "control", "hb"]

    cfg: cfg_t = {f"{c}_port": get_port(ip) for c in channels}

    cfg["ip"] = ip
    cfg["key"] = uuid.uuid4().hex
    cfg["transport"] = transport
    cfg["signature_scheme"] = signature_scheme
    cfg["kernel_name"] = kernel_name

    f.write(json.dumps(cfg, indent=2))
    f.close()

    return fname, cfg


def read_connection_file(fname: str) -> cfg_t:
    with open(fname, "rt") as f:
        cfg: cfg_t = json.load(f)

    return cfg


async def launch_kernel(
    kernelspec_path: str,
    connection_file_path: str,
    kernel_cwd: str,
    capture_output: bool,
) -> asyncio.subprocess.Process:
    with open(kernelspec_path) as f:
        kernelspec = json.load(f)
    cmd = [s.format(connection_file=connection_file_path) for s in kernelspec["argv"]]
    if kernel_cwd:
        prev_dir = os.getcwd()
        os.chdir(kernel_cwd)
    if capture_output:
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.STDOUT
        )
    else:
        p = await asyncio.create_subprocess_exec(*cmd)
    if kernel_cwd:
        os.chdir(prev_dir)
    return p


def create_socket(channel: str, cfg: cfg_t, identity: Optional[bytes] = None) -> Socket:
    ip = cfg["ip"]
    port = cfg[f"{channel}_port"]
    url = f"tcp://{ip}:{port}"
    socket_type = channel_socket_types[channel]
    sock = context.socket(socket_type)
    sock.linger = 1000  # set linger to 1s to prevent hangs at exit
    if identity:
        sock.identity = identity
    sock.connect(url)
    return sock


def connect_channel(
    channel_name: str, cfg: cfg_t, identity: Optional[bytes] = None
) -> Socket:
    sock = create_socket(channel_name, cfg, identity)
    if channel_name == "iopub":
        sock.setsockopt(zmq.SUBSCRIBE, b"")
    return sock
