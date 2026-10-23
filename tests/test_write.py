import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio
import httpx2
import pytest
from fps import Module
from jpterm.write import write_document
from jupyter_ydoc import YFile, YNotebook
from rich.text import Text
from textual.app import App
from txl_remote_contents.main import RemoteContents

from txl.base import Contents


@pytest.fixture
def notebook():
    document = YNotebook()
    document.source = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"custom": "preserved"},
        "cells": [
            {"id": "code", "cell_type": "code", "source": "old code",
             "metadata": {"custom": "preserved"}, "execution_count": 7,
             "outputs": [{"output_type": "stream", "name": "stdout", "text": "old output"}]},
            {"id": "markdown", "cell_type": "markdown", "source": "old markdown",
             "metadata": {}},
        ],
    }
    return document


@pytest.fixture
def write_with_contents():
    def run(contents, path, source, cell_id=None):
        class TestModule(Module):
            async def start(self):
                self.put(contents, Contents)
                self.put(App(), App)

        with patch("txl.app.modules", {"test": TestModule}):
            anyio.run(write_document, path, source, cell_id, [], 5)

    return run


@pytest.mark.parametrize("cell_id", ["code", "markdown"])
def test_write_cell_preserves_other_content(notebook, write_with_contents, cell_id):
    before = notebook.source
    contents = SimpleNamespace(get=AsyncMock(return_value=notebook), save=AsyncMock())
    write_with_contents(contents, "test.ipynb", "new source\n", cell_id)
    expected = before
    cell = next(cell for cell in expected["cells"] if cell["id"] == cell_id)
    cell["source"] = "new source\n"
    if cell_id == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    assert notebook.source == expected
    contents.save.assert_awaited_once_with("test.ipynb", notebook)


def test_unchanged_cell_keeps_outputs(notebook, write_with_contents):
    before = notebook.source
    contents = SimpleNamespace(get=AsyncMock(return_value=notebook), save=AsyncMock())
    write_with_contents(contents, "test.ipynb", "old code", "code")
    assert notebook.source == before
    contents.save.assert_not_awaited()


def test_unknown_cell_does_not_save(notebook, write_with_contents):
    before = notebook.source
    contents = SimpleNamespace(get=AsyncMock(return_value=notebook), save=AsyncMock())
    with pytest.raises(ValueError, match="Cell ID not found: missing"):
        write_with_contents(contents, "test.ipynb", "new source", "missing")
    assert notebook.source == before
    contents.save.assert_not_awaited()


@pytest.mark.parametrize("error", [PermissionError("denied"), RuntimeError("connection failed")])
def test_text_load_errors_do_not_save(write_with_contents, error):
    contents = SimpleNamespace(get=AsyncMock(side_effect=error), save=AsyncMock())
    with pytest.raises(type(error), match=str(error)):
        write_with_contents(contents, "file.txt", "new source")
    contents.save.assert_not_awaited()


@pytest.fixture
def run_write(tmp_path):
    def run(*arguments, input=None, env=None):
        result = subprocess.run(
            [sys.executable, "-c", "from jpterm.cli import main; main()", *arguments],
            input=input, capture_output=True, text=True, encoding="utf-8", cwd=tmp_path,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1", **(env or {})},
            timeout=20,
        )
        result.stdout = Text.from_ansi(result.stdout).plain
        result.stderr = Text.from_ansi(result.stderr).plain
        return result
    return run


@pytest.mark.parametrize("exists", [False, True])
@pytest.mark.parametrize("source", ["", "hello π\nsecond line\n"])
def test_write_local_text(run_write, tmp_path, exists, source):
    path = tmp_path / "LICENSE"
    if exists:
        path.write_text("old content", encoding="utf-8")
    result = run_write("write", "LICENSE", "--source", source)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert path.read_text(encoding="utf-8") == source


def test_write_stdin(run_write, tmp_path):
    source = "first line\nsecond line π\n"
    result = run_write("write", "script.py", "--stdin", input=source)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "script.py").read_text(encoding="utf-8") == source


def test_unicode_file_with_non_utf8_locale(run_write, tmp_path):
    source = "Unicode text: π\n"
    env = {"PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"}
    result = run_write("write", "file.txt", "--stdin", input=source, env=env)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == source
    result = run_write("show", "file.txt", "--json", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == source


def test_write_local_notebook(run_write, tmp_path, notebook):
    path = tmp_path / "test.ipynb"
    path.write_text(json.dumps(notebook.source), encoding="utf-8")
    result = run_write("write", "test.ipynb", "--cell", "code", "--source", "print(42)")
    assert result.returncode == 0, result.stderr
    cell = json.loads(path.read_text(encoding="utf-8"))["cells"][0]
    assert cell["source"] == "print(42)"
    assert cell["outputs"] == []
    assert cell["execution_count"] is None


@pytest.mark.parametrize("arguments, message", [
    (["write", "file.txt"], "Provide exactly one"),
    (["write", "file.txt", "--source", "text", "--stdin"], "Provide exactly one"),
    (["write", "file.txt", "--cell", "code", "--source", "text"], "requires a notebook"),
    (["write", "test.ipynb", "--source", "text"], "requires --cell"),
    (["--collaborative", "write", "file.txt", "--source", "text"], "requires --server"),
])
def test_invalid_write(run_write, tmp_path, arguments, message):
    result = run_write(*arguments)
    assert result.returncode != 0
    assert message in result.stderr
    assert not list(tmp_path.iterdir())


def test_remote_save_reports_http_error():
    async def check():
        response = httpx2.Response(
            403, request=httpx2.Request("PUT", "http://server/api/contents/file.txt")
        )
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.put.return_value = response
        contents = RemoteContents("http://server", {}, httpx2.Cookies(), False, None)
        with patch("txl_remote_contents.main.httpx2.AsyncClient", return_value=client):
            with pytest.raises(httpx2.HTTPStatusError):
                await contents.save("file.txt", SimpleNamespace(source="text"))

    anyio.run(check)


def test_collaborative_save_uses_shared_document():
    async def check():
        document = YFile()
        document.source = "new content"
        document.dirty = True
        contents = RemoteContents("http://server", {}, httpx2.Cookies(), True, None)
        contents.document_id[document] = "room"
        with patch("txl_remote_contents.main.httpx2.AsyncClient") as client:
            await contents.save("file.txt", document)
            assert document.dirty
            client.assert_not_called()

    anyio.run(check)


def test_write_cell_preserves_unchanged_text(notebook, write_with_contents):
    text = notebook.ycells[0]["source"]
    text.clear()
    text += "π😀 hello world"
    events = []
    subscription = text.observe(lambda event: events.append(event.delta))
    contents = SimpleNamespace(get=AsyncMock(return_value=notebook), save=AsyncMock())
    write_with_contents(contents, "test.ipynb", "π😀 hello there", "code")
    assert str(text) == "π😀 hello there"
    assert events[0][0] == {"retain": len("π😀 hello ".encode("utf-8"))}
    text.unobserve(subscription)
