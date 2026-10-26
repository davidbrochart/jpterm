"""Notebook kernel sessions shared by the CLI and TUI."""

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

import anyio
import psutil

from .connect import kernel_command, write_connection_file
from .kernelspec import find_kernelspec
from .paths import jupyter_runtime_dir

# Keep child handles available for reaping while this process is alive.
_children = []


def runtime_directory():
    directory = Path(jupyter_runtime_dir()) / "jpterm"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def session_process(record):
    """Check process identity as well as PID, which may have been reused."""
    try:
        process = psutil.Process(record["pid"])
        if (process.create_time() == record["created"]
                and process.status() != psutil.STATUS_ZOMBIE):
            return process
    except psutil.NoSuchProcess:
        pass
    return None


def list_sessions():
    records = []
    for path in sorted(runtime_directory().glob("*.session.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records.append({
            "path": record["path"], "kernel_name": record["kernel_name"],
            "pid": record["pid"], "alive": session_process(record) is not None,
        })
    return records


class LocalSession:
    def __init__(self, path, timeout=30):
        self.path = os.path.normcase(str(Path(path).resolve()))
        self.timeout = timeout
        digest = hashlib.sha256(self.path.encode("utf-8")).hexdigest()
        directory = runtime_directory()
        self.record_path = directory / f"{digest}.session.json"
        self.connection_path = directory / f"{digest}.connection.json"
        self.launched = False

    def read(self):
        try:
            record = json.loads(self.record_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if record["path"] != self.path:
            raise ValueError("Local kernel session path does not match notebook")
        return record

    def connection_file(self, kernel_name):
        self.launched = False
        record = self.read()
        if record is not None and session_process(record) is not None:
            if not self.connection_path.exists():
                raise ValueError("Kernel connection file is missing; stop the kernel first")
            return str(self.connection_path)
        spec = find_kernelspec(kernel_name)
        if not spec:
            raise ValueError("Could not find a kernel; provide --kernel NAME or install one")
        # Create private connection files even when replacing a stale session.
        fd = os.open(self.connection_path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        os.close(fd)
        write_connection_file(str(self.connection_path))
        command = kernel_command(spec, str(self.connection_path))
        environment = dict(os.environ)
        # Detached kernels must not monitor the lifetime of this CLI process.
        for key in ("JPY_PARENT_PID", "JPY_INTERRUPT_EVENT"):
            environment.pop(key, None)
        options = (
            {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt" else {"start_new_session": True}
        )
        process = None
        temporary = self.record_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            process = subprocess.Popen(
                command, cwd=Path(self.path).parent, env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, **options,
            )
            record = {
                "path": self.path, "kernel_name": kernel_name, "pid": process.pid,
                "created": psutil.Process(process.pid).create_time(),
            }
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
            os.replace(temporary, self.record_path)
        except BaseException:
            if process is not None:
                process.kill()
                process.wait()
            self.connection_path.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
            raise
        _children[:] = [child for child in _children if child.poll() is None]
        _children.append(process)
        self.launched = True
        return str(self.connection_path)

    async def stop(self, expected_record=None):
        record = self.read()
        if record is None or (expected_record is not None and record != expected_record):
            return False
        process = session_process(record)
        if process is not None:
            # Check creation time again inside psutil before signaling a PID.
            process.kill()
            with anyio.fail_after(self.timeout):
                while session_process(record) is not None:
                    await anyio.sleep(0.05)
        _children[:] = [child for child in _children if child.poll() is None]
        self.record_path.unlink(missing_ok=True)
        self.connection_path.unlink(missing_ok=True)
        return True
