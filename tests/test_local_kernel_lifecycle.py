import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import anyio
import psutil
from txl_local_kernels.driver import KernelDriver
from txl_local_kernels.sessions import LocalSession, process_alive


def test_stop_waits_for_channel_readers_before_closing_sockets():
    async def check():
        stopped = set()

        async def reader(name, ready):
            ready.set()
            try:
                await anyio.sleep_forever()
            finally:
                with anyio.CancelScope(shield=True):
                    await anyio.sleep(0.01)
                    stopped.add(name)

        async with anyio.create_task_group() as tasks:
            driver = KernelDriver.__new__(KernelDriver)
            driver.launch = False
            driver.owned_session = None
            driver.channel_tasks = []
            for name in ("shell", "iopub"):
                ready = anyio.Event()
                driver.channel_tasks.append(tasks.create_task(reader(name, ready)))
                await ready.wait()

            def close(**kwargs):
                assert stopped == {"shell", "iopub"}

            for channel in ("shell_channel", "control_channel", "iopub_channel"):
                setattr(driver, channel, SimpleNamespace(close=Mock(side_effect=close)))
            await driver.stop()
            for channel in ("shell_channel", "control_channel", "iopub_channel"):
                getattr(driver, channel).close.assert_called_once_with(linger=0)

    anyio.run(check)


def test_stop_terminates_launcher_and_child_interpreter(tmp_path, monkeypatch):
    monkeypatch.setenv("JUPYTER_RUNTIME_DIR", str(tmp_path / "runtime"))
    child_pid_path = tmp_path / "child.pid"
    script = (
        "import pathlib, subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid))\n"
        "child.wait()\n"
    )

    async def check():
        session = LocalSession(tmp_path / "test.ipynb")
        with patch("txl_local_kernels.sessions.kernel_command", return_value=[
            sys.executable, "-c", script,
        ]):
            session.connection_file("python3")
        try:
            with anyio.fail_after(10):
                while not child_pid_path.exists():
                    await anyio.sleep(0.02)
                # Creation may be visible before the PID has been written.
                while not child_pid_path.read_text():
                    await anyio.sleep(0.02)
            child = psutil.Process(int(child_pid_path.read_text()))
            record = json.loads(session.record_path.read_text())
            launcher = psutil.Process(record["pid"])
            assert child.pid != launcher.pid
            descendants = launcher.children(recursive=True)
            assert await session.stop()
            assert not process_alive(launcher)
            assert not process_alive(child)
            assert all(not process_alive(process) for process in descendants)
            assert not session.record_path.exists()
            assert not session.connection_path.exists()
        finally:
            await session.stop()

    anyio.run(check)
