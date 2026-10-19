"""CLI integration checks against a real, non-collaborative Jupyverse server."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import httpx2
import pytest
from rich.text import Text


@pytest.fixture(scope="module")
def jupyverse_server(tmp_path_factory):
    server = SimpleNamespace()
    root = tmp_path_factory.mktemp("server-cli")
    executable = os.environ.get("JUPYVERSE_EXECUTABLE") or shutil.which("jupyverse")
    if executable is None:
        pytest.skip("Install jupyverse[jupyterlab,noauth] to run server tests")
    server_root = root / "server"
    server.client_root = root / "client"
    server_root.mkdir()
    server.client_root.mkdir()
    server.source_lines = [f"# server_cell_line_{index:02}" for index in range(40)]
    server.source_lines.append("raise RuntimeError('show must not execute this cell')")
    server.notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "name": "must-not-start",
                "display_name": "Must not start",
                "language": "python",
            }
        },
        "cells": [
            {"id": "other-cell", "cell_type": "markdown", "metadata": {},
             "source": "unselected_cell_content"},
            {
                "id": "server-cell",
                "cell_type": "code",
                "metadata": {},
                "source": "\n".join(server.source_lines),
                "execution_count": 7,
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": "saved_server_output\n"}
                ],
            }
        ],
    }
    (server_root / "remote.ipynb").write_text(json.dumps(server.notebook), encoding="utf-8")
    (server_root / "writable.ipynb").write_text(json.dumps(server.notebook), encoding="utf-8")
    server.text = "SERVER LICENSE\n\nOnly available from the server.\n"
    # Write exact bytes so Windows does not translate LF into CRLF.
    (server_root / "LICENSE").write_bytes(server.text.encode("utf-8"))
    server.crlf_text = server.text.replace("\n", "\r\n")
    (server_root / "LICENSE_CRLF").write_bytes(server.crlf_text.encode("utf-8"))
    server.markdown = "# Server heading\n\n" + "\n\n".join(
        (f"server_paragraph_{index:02}" for index in range(30))
    )
    (server_root / "remote.md").write_text(server.markdown, encoding="utf-8")
    for name in ("remote.ipynb", "LICENSE", "LICENSE_CRLF", "remote.md"):
        (server.client_root / name).write_text("WRONG_LOCAL_CONTENT", encoding="utf-8")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server.url = f"http://127.0.0.1:{port}"
    server.log_path = root / "server.log"
    with server.log_path.open("w", encoding="utf-8") as log:
        server.process = subprocess.Popen(
            [executable, "--host", "127.0.0.1", "--port", str(port), "--timeout", "10"],
            cwd=server_root,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONUTF8="1"),
        )
        try:
            deadline = time.monotonic() + 20
            ready = False
            with httpx2.Client(trust_env=False, timeout=0.5) as client:
                while time.monotonic() < deadline:
                    if server.process.poll() is not None:
                        break
                    try:
                        response = client.get(f"{server.url}/api/contents/remote.ipynb")
                        if response.status_code == 200:
                            ready = True
                            break
                    except httpx2.HTTPError:
                        pass
                    time.sleep(0.1)
            if not ready:
                server_log = server.log_path.read_text(encoding="utf-8")
                pytest.fail(f"Jupyverse did not become ready:\n{server_log}")
            yield server
        finally:
            if server.process.poll() is None:
                server.process.terminate()
                try:
                    server.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.process.kill()
                    server.process.wait(timeout=5)


@pytest.fixture
def run_cli(jupyverse_server):

    def run(*arguments, expected_code=0, command="show", input=None):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8", NO_COLOR="1", COLUMNS="80")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from jpterm.cli import main; main()",
                "--server",
                jupyverse_server.url,
                command,
                *arguments,
            ],
            cwd=jupyverse_server.client_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=input,
            timeout=20,
        )
        result.stdout = Text.from_ansi(result.stdout).plain
        result.stderr = Text.from_ansi(result.stderr).plain
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert "WRONG_LOCAL_CONTENT" not in result.stdout + result.stderr
        assert "Traceback" not in result.stderr
        return result

    return run


@pytest.mark.parametrize("show_cell_ids", [False, True])
def test_show_notebook(run_cli, jupyverse_server, show_cell_ids):
    arguments = ["remote.ipynb"]
    if show_cell_ids:
        arguments.append("--show-cell-ids")
    result = run_cli(*arguments)
    output = result.stdout + result.stderr
    assert ("In [7]: server-cell" in output) == show_cell_ids
    assert ("In []: other-cell" in output) == show_cell_ids
    for line in jupyverse_server.source_lines:
        assert output.count(line) == 1
    assert output.count("saved_server_output") == 1
    assert "In [7]" in output
    with httpx2.Client(trust_env=False) as client:
        response = client.get(f"{jupyverse_server.url}/api/kernels")
        response.raise_for_status()
        assert response.json() == []


@pytest.mark.parametrize("path", ["remote.ipynb", "LICENSE", "LICENSE_CRLF"])
def test_show_json(run_cli, jupyverse_server, path):
    source = json.loads(run_cli(path, "--json").stdout)
    if path == "LICENSE":
        assert source == jupyverse_server.text
    elif path == "LICENSE_CRLF":
        assert source == jupyverse_server.crlf_text
    else:
        cell = source["cells"][1]
        assert cell["id"] == "server-cell"
        assert cell["source"] == jupyverse_server.notebook["cells"][1]["source"]
        assert cell["execution_count"] == 7


@pytest.mark.parametrize("as_json", [False, True])
def test_show_cell(run_cli, jupyverse_server, as_json):
    arguments = ["remote.ipynb", "--cell", "server-cell"]
    if as_json:
        arguments.append("--json")
    result = run_cli(*arguments)
    if as_json:
        notebook = json.loads(run_cli("remote.ipynb", "--json").stdout)
        assert json.loads(result.stdout) == notebook["cells"][1]
    else:
        output = result.stdout + result.stderr
        assert "unselected_cell_content" not in output
        assert output.count("saved_server_output") == 1
        for line in jupyverse_server.source_lines:
            assert output.count(line) == 1


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("path, message", [
    ("remote.ipynb", "Cell ID not found: missing"),
    ("LICENSE", "--cell requires a notebook"),
])
def test_invalid_cell_selection(run_cli, as_json, path, message):
    arguments = [path, "--cell", "missing"]
    if as_json:
        arguments.append("--json")
    result = run_cli(*arguments, expected_code=1)
    assert message in result.stderr


def test_show_plain_text(run_cli, jupyverse_server):
    result = run_cli("LICENSE")
    output = result.stdout + result.stderr
    assert [line.rstrip() for line in output.splitlines()] == jupyverse_server.text.splitlines()


def test_show_markdown(run_cli, jupyverse_server):
    result = run_cli("remote.md")
    output = result.stdout + result.stderr
    assert output.count("Server heading") == 1
    for index in range(30):
        assert output.count(f"server_paragraph_{index:02}") == 1


def test_missing_file(run_cli, jupyverse_server):
    result = run_cli("missing.ipynb", expected_code=1)
    assert "404" in result.stderr


@pytest.mark.parametrize("from_stdin", [False, True])
def test_write_server_text(run_cli, jupyverse_server, from_stdin):
    path = f"written-{from_stdin}.txt"
    source = "server write π\nsecond line\n"
    arguments = [path, "--stdin"] if from_stdin else [path, "--source", source]
    run_cli(*arguments, command="write", input=source if from_stdin else None)
    # Jupyverse writes text using the server platform's native line endings.
    assert json.loads(run_cli(path, "--json").stdout) == source.replace("\n", os.linesep)
    assert not (jupyverse_server.client_root / path).exists()
    run_cli(path, "--source", "", command="write")
    assert json.loads(run_cli(path, "--json").stdout) == ""


def test_write_server_cell(run_cli):
    path = "writable.ipynb"
    before = json.loads(run_cli(path, "--json").stdout)
    run_cli(path, "--cell", "server-cell", "--source", "print(42)", command="write")
    after = json.loads(run_cli(path, "--json").stdout)
    before["cells"][1].update(source="print(42)", outputs=[], execution_count=None)
    assert after == before
    result = run_cli(path, "--cell", "missing", "--source", "bad", command="write", expected_code=1)
    assert "Cell ID not found" in result.stderr
    assert json.loads(run_cli(path, "--json").stdout) == after
