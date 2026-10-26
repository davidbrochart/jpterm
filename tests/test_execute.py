import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio
import pytest
from fps import Module
from jpterm.execute import execute_notebook
from jupyter_ydoc import YNotebook
from textual.app import App

from txl.base import Contents, Kernels


def test_execute_cell_requires_server(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from jpterm.cli import main; main()",
         "execute", "notebook.ipynb", "--cell", "code"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"},
    )
    assert result.returncode == 2
    assert "--cell requires --server" in result.stderr
    assert not list(tmp_path.iterdir())


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
            self.put(lambda *args, **kwargs: SimpleNamespace(execute=execute, aclose=AsyncMock()), Kernels)
            self.put(App(), App)

    with patch("txl.app.modules", {"test": TestModule}):
        errors = anyio.run(execute_notebook, "test.ipynb", None, [], 5)
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
                 "assert counter == 1\nprint(Path('input.txt').read_text())"
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
    if os.name == "posix":
        with pytest.raises(ProcessLookupError):
            os.kill(info["pid"], 0)


def test_local_execution_uses_fresh_kernel_and_notebook_directory(tmp_path, local_notebook):
    path, source = local_notebook
    for _ in range(2):
        result = run_local(tmp_path, "notebooks/test.ipynb", "--json")
        assert result.returncode == 0, result.stdout + result.stderr
        notebook = json.loads(result.stdout)
        saved = YNotebook()
        saved.source = json.loads(path.read_text(encoding="utf-8"))
        assert notebook == saved.source
        assert notebook["cells"][0] == source["cells"][0]
        info = json.loads("".join(notebook["cells"][1]["outputs"][0]["text"]))
        assert info["counter"] == 1
        assert notebook["cells"][2]["execution_count"] == 2
        assert "".join(notebook["cells"][2]["outputs"][0]["text"]) == "relative input\n"
        assert_kernel_stopped(info)


@pytest.mark.parametrize("timeout", [False, True])
def test_local_execution_cleans_up_on_failure(tmp_path, local_notebook, timeout):
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
    assert_kernel_stopped(info)
    if timeout:
        assert "Timed out executing notebook" in result.stderr
        assert json.loads(path.read_text(encoding="utf-8")) == source
    else:
        assert "ValueError: cell failed" in result.stderr
        notebook = json.loads(result.stdout)
        assert notebook["cells"][2]["outputs"][0]["output_type"] == "error"
        saved = YNotebook()
        saved.source = json.loads(path.read_text(encoding="utf-8"))
        assert notebook == saved.source
