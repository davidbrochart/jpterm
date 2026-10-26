import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio
import psutil
import pytest
from fps import Module
from jpterm.execute import execute_notebook
from jupyter_ydoc import YNotebook
from rich.text import Text
from textual.app import App
from txl_cell.main import _Cell
from txl_local_kernels.main import LocalKernels, LocalKernelsModule
from txl_notebook_editor.main import NotebookEditor

from txl.base import Contents, Kernels


@pytest.fixture(autouse=True)
def isolated_sessions(tmp_path, monkeypatch):
    from txl_local_kernels.sessions import LocalSession, list_sessions

    monkeypatch.setenv("JUPYTER_RUNTIME_DIR", str(tmp_path / "runtime"))
    yield

    async def cleanup():
        for record in list_sessions():
            await LocalSession(record["path"]).stop()

    anyio.run(cleanup)


@pytest.mark.parametrize("fail", [False, True])
def test_save_once_after_execution(fail):
    document = YNotebook()
    document.source = {
        "nbformat": 4, "nbformat_minor": 5, "metadata": {},
        "cells": [
            {"id": str(i), "cell_type": "code", "source": str(i),
             "metadata": {}, "outputs": [], "execution_count": None}
            for i in range(3)
        ],
    }
    contents = SimpleNamespace(get=AsyncMock(return_value=document), save=AsyncMock())
    executed = []

    async def execute(cell):
        contents.save.assert_not_awaited()
        executed.append(str(cell["id"]))
        if fail and cell["id"] == "1":
            cell["outputs"].append({
                "output_type": "error", "ename": "ValueError", "evalue": "failed",
                "traceback": [],
            })

    class TestModule(Module):
        async def start(self):
            self.put(contents, Contents)
            self.put(
                lambda *args, **kwargs: SimpleNamespace(execute=execute, aclose=AsyncMock()),
                Kernels,
            )
            self.put(App(), App)

    with patch("txl.app.modules", {"test": TestModule}):
        errors = anyio.run(execute_notebook, "test.ipynb", None, [], 5, None, True)
    assert executed == (["0", "1"] if fail else ["0", "1", "2"])
    assert bool(errors) == fail
    contents.save.assert_awaited_once_with("test.ipynb", document)


@pytest.fixture
def local_notebook(tmp_path):
    directory = tmp_path / "notebooks"
    directory.mkdir()
    (directory / "input.txt").write_text("relative input", encoding="utf-8")
    source = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {
            "name": "python3", "display_name": "Python 3", "language": "python",
        }},
        "cells": [
            {"id": "markdown", "cell_type": "markdown", "metadata": {}, "source": "# Title"},
            {"id": "define", "cell_type": "code", "metadata": {}, "outputs": [],
             "execution_count": None, "source": (
                 "import os, json, ipykernel\nfrom pathlib import Path\n"
                 "counter = globals().get('counter', 0) + 1\n"
                 "info = {'pid': os.getpid(), 'connection': ipykernel.get_connection_file(), "
                 "'counter': counter}\n"
                 "Path('kernel-info.json').write_text(json.dumps(info))\n"
                 "print(json.dumps(info))"
             )},
            {"id": "read", "cell_type": "code", "metadata": {}, "outputs": [],
             "execution_count": None, "source": (
                 "assert counter >= 1\nprint(Path('input.txt').read_text())"
             )},
        ],
    }
    path = directory / "test.ipynb"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path, source


def run_local(tmp_path, *arguments):
    return subprocess.run(
        [sys.executable, "-c", "from jpterm.cli import main; main()", "execute", *arguments],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=25,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"},
    )


def assert_kernel_stopped(info):
    assert not Path(info["connection"]).exists()
    try:
        assert psutil.Process(info["pid"]).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass


def test_local_execution_reuses_kernel_and_notebook_directory(tmp_path, local_notebook):
    path, source = local_notebook
    previous_pid = None
    for iteration in range(1, 3):
        result = run_local(tmp_path, "notebooks/test.ipynb", "--json")
        assert result.returncode == 0, result.stdout + result.stderr
        notebook = json.loads(result.stdout)
        saved = YNotebook()
        saved.source = json.loads(path.read_text(encoding="utf-8"))
        assert notebook == saved.source
        assert notebook["cells"][0] == source["cells"][0]
        info = json.loads("".join(notebook["cells"][1]["outputs"][0]["text"]))
        assert info["counter"] == iteration
        if previous_pid is not None:
            assert info["pid"] == previous_pid
        previous_pid = info["pid"]
        assert notebook["cells"][2]["execution_count"] == iteration * 2
        assert "".join(notebook["cells"][2]["outputs"][0]["text"]) == "relative input\n"
        assert Path(info["connection"]).exists()
        assert not list((tmp_path / "runtime").rglob("*.lock"))


@pytest.mark.parametrize("timeout", [False, True])
def test_local_execution_preserves_kernel_on_failure(tmp_path, local_notebook, timeout):
    path, source = local_notebook
    source["cells"][2]["source"] = (
        "import time; time.sleep(60)" if timeout else "raise ValueError('cell failed')"
    )
    path.write_text(json.dumps(source), encoding="utf-8")
    arguments = [str(path), "--json"]
    if timeout:
        arguments.extend(["--timeout", "5"])
    result = run_local(tmp_path, *arguments)
    assert result.returncode == 1, result.stdout + result.stderr
    info = json.loads((path.parent / "kernel-info.json").read_text(encoding="utf-8"))
    assert Path(info["connection"]).exists()
    assert psutil.Process(info["pid"]).is_running()
    if timeout:
        assert "Timed out executing notebook" in result.stderr
        assert json.loads(path.read_text(encoding="utf-8")) == source
        # A busy kernel must not be mistaken for a dead one and replaced.
        result = run_local(tmp_path, str(path), "--cell", "define", "--timeout", "0.5")
        assert result.returncode == 1, result.stdout + result.stderr
        sessions = json.loads(kernel_command(tmp_path, "list", "--json").stdout)
        assert len(sessions) == 1
        assert sessions[0]["pid"] == info["pid"]
    else:
        assert "ValueError: cell failed" in result.stderr
        notebook = json.loads(result.stdout)
        assert notebook["cells"][2]["outputs"][0]["output_type"] == "error"
        saved = YNotebook()
        saved.source = json.loads(path.read_text(encoding="utf-8"))
        assert notebook == saved.source


@pytest.mark.parametrize("cell_id, message", [
    ("missing", "Cell ID not found"), ("markdown", "Cell is not a code cell"),
])
@pytest.mark.parametrize("force_color", ["0", "1"])
def test_invalid_local_cell(tmp_path, local_notebook, monkeypatch, cell_id, message, force_color):
    path, source = local_notebook
    monkeypatch.setenv("FORCE_COLOR", force_color)
    result = run_local(tmp_path, str(path), "--cell", cell_id)
    assert result.returncode == 1, result.stdout + result.stderr
    assert message in Text.from_ansi(result.stderr).plain
    assert json.loads(path.read_text(encoding="utf-8")) == source
    assert not list((tmp_path / "runtime").rglob("*.session.json"))


def kernel_command(tmp_path, *arguments):
    return subprocess.run(
        [sys.executable, "-c", "from jpterm.cli import main; main()", "kernel", *arguments],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=15,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"},
    )


def test_local_cells_share_state_and_can_be_stopped(tmp_path, local_notebook):
    path, source = local_notebook
    # This fails in a fresh kernel: earlier cells must not be executed implicitly.
    result = run_local(tmp_path, "notebooks/../notebooks/test.ipynb", "--cell", "read", "--json")
    assert result.returncode == 1
    assert "NameError" in Text.from_ansi(result.stderr).plain
    result = run_local(tmp_path, str(path), "--cell", "define", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    cell = json.loads(result.stdout)
    info = json.loads("".join(cell["outputs"][0]["text"]))
    assert cell["execution_count"] == 2
    result = run_local(tmp_path, str(path), "--cell", "read", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["execution_count"] == 3
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["cells"][0] == source["cells"][0]
    assert saved["cells"][1]["execution_count"] == 2
    result = kernel_command(tmp_path, "list", "--json")
    assert result.returncode == 0, result.stderr
    sessions = json.loads(result.stdout)
    assert len(sessions) == 1
    assert sessions[0]["pid"] == info["pid"]
    assert sessions[0]["alive"]
    assert "key" not in sessions[0]
    if os.name == "posix":
        assert Path(info["connection"]).stat().st_mode & 0o077 == 0
    result = kernel_command(tmp_path, "stop", str(path))
    assert result.returncode == 0, result.stderr
    assert_kernel_stopped(info)
    assert json.loads(kernel_command(tmp_path, "list", "--json").stdout) == []
    result = run_local(tmp_path, str(path), "--cell", "define", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["execution_count"] == 1


def test_local_kernel_start_is_ready_and_preserves_notebook(tmp_path, local_notebook):
    path, source = local_notebook
    # An explicit kernel must override the notebook's kernelspec on first launch.
    source["metadata"]["kernelspec"]["name"] = "not-installed"
    path.write_text(json.dumps(source), encoding="utf-8")
    before = path.read_bytes()
    result = kernel_command(tmp_path, "start", str(path), "--kernel", "python3")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
    assert path.read_bytes() == before
    assert not (path.parent / "kernel-info.json").exists()
    sessions = json.loads(kernel_command(tmp_path, "list", "--json").stdout)
    assert len(sessions) == 1
    assert sessions[0]["alive"]
    result = run_local(tmp_path, str(path), "--cell", "define", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["execution_count"] == 1
    before = path.read_bytes()
    result = kernel_command(tmp_path, "start", str(path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes() == before
    assert json.loads(kernel_command(tmp_path, "list", "--json").stdout) == sessions
    result = run_local(tmp_path, str(path), "--cell", "read", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["execution_count"] == 2


@pytest.mark.parametrize("path, message", [
    ("file.txt", "requires a notebook"), ("missing.ipynb", "File not found"),
])
def test_invalid_local_kernel_start(tmp_path, path, message):
    result = kernel_command(tmp_path, "start", path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert message in Text.from_ansi(result.stderr).plain
    assert not list((tmp_path / "runtime").rglob("*.session.json"))


def test_dead_local_kernel_is_replaced(tmp_path, local_notebook):
    path, _ = local_notebook
    result = run_local(tmp_path, str(path), "--cell", "define", "--json")
    assert result.returncode == 0, result.stderr
    info = json.loads("".join(json.loads(result.stdout)["outputs"][0]["text"]))
    psutil.Process(info["pid"]).kill()
    # Wait for the killed process to exit before requesting a new session.
    import time

    for _ in range(100):
        try:
            if psutil.Process(info["pid"]).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.02)
    result = run_local(tmp_path, str(path), "--cell", "define", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    cell = json.loads(result.stdout)
    assert cell["execution_count"] == 1
    assert json.loads("".join(cell["outputs"][0]["text"]))["counter"] == 1


def test_stop_does_not_signal_a_reused_pid(tmp_path):
    from txl_local_kernels.sessions import LocalSession

    async def check():
        session = LocalSession(tmp_path / "test.ipynb")
        session.record_path.write_text(json.dumps({
            "path": session.path, "pid": 12345, "created": 1.0,
        }), encoding="utf-8")
        with patch("txl_local_kernels.sessions.psutil.Process") as factory:
            process = factory.return_value
            process.create_time.return_value = 2.0
            assert await session.stop()
            process.kill.assert_not_called()
        assert not session.record_path.exists()
    anyio.run(check)


@pytest.mark.parametrize("ownership", ["owned", "attached", "replaced"])
def test_tui_attaches_by_notebook_path_and_respects_ownership(tmp_path, local_notebook, ownership):
    path, source = local_notebook
    if ownership == "attached":
        result = kernel_command(tmp_path, "start", str(path))
        assert result.returncode == 0, result.stdout + result.stderr

    info = {}

    async def check():
        with anyio.fail_after(40):
            async with anyio.create_task_group() as tasks:
                class TuiKernels(LocalKernels):
                    task_group = tasks

                module = LocalKernelsModule("local_kernels")
                module.tg = tasks
                document = YNotebook()
                document.source = source
                contents = SimpleNamespace(get=AsyncMock(return_value=document))

                def cell_factory(cell, language, kernel):
                    return _Cell(cell, language, kernel, contents, None, tasks)

                app = App()
                app.cli = False
                try:
                    async with app.run_test():
                        editor = NotebookEditor(
                            tasks, contents, TuiKernels, {}, cell_factory, SimpleNamespace(
                                set_dirty=lambda editor: None, clear_dirty=lambda editor: None,
                            ),
                        )
                        await app.screen.mount(editor)
                        await editor.open(str(path))
                        await editor.kernel.execute(document.ycells[1])
                        info.update(json.loads(
                            (path.parent / "kernel-info.json").read_text(encoding="utf-8")
                        ))
                        result = await anyio.to_thread.run_sync(
                            lambda: run_local(tmp_path, str(path), "--cell", "read", "--json")
                        )
                        assert result.returncode == 0, result.stdout + result.stderr
                        assert json.loads(result.stdout)["execution_count"] == 2
                        await editor.remove()
                        result = await anyio.to_thread.run_sync(
                            lambda: run_local(tmp_path, str(path), "--cell", "read", "--json")
                        )
                        assert result.returncode == 0, result.stdout + result.stderr
                        assert json.loads(result.stdout)["execution_count"] == 3
                        if ownership == "replaced":
                            result = await anyio.to_thread.run_sync(
                                lambda: kernel_command(tmp_path, "stop", str(path))
                            )
                            assert result.returncode == 0, result.stderr
                            result = await anyio.to_thread.run_sync(
                                lambda: run_local(tmp_path, str(path), "--cell", "define", "--json")
                            )
                            assert result.returncode == 0, result.stdout + result.stderr
                            info.update(json.loads(
                                (path.parent / "kernel-info.json").read_text(encoding="utf-8")
                            ))
                finally:
                    await module.stop()

    anyio.run(check)
    sessions = json.loads(kernel_command(tmp_path, "list", "--json").stdout)
    if ownership == "owned":
        assert sessions == []
        assert_kernel_stopped(info)
    else:
        assert len(sessions) == 1
        assert sessions[0]["pid"] == info["pid"]
        assert sessions[0]["alive"]
        result = run_local(tmp_path, str(path), "--cell", "read", "--json")
        assert result.returncode == 0, result.stdout + result.stderr
