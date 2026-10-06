"""CLI integration checks against a real, non-collaborative Jupyverse server."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import httpx
import pytest


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
    server.text = "SERVER LICENSE\n\nOnly available from the server.\n"
    (server_root / "LICENSE").write_text(server.text, encoding="utf-8")
    server.markdown = "# Server heading\n\n" + "\n\n".join(
        (f"server_paragraph_{index:02}" for index in range(30))
    )
    (server_root / "remote.md").write_text(server.markdown, encoding="utf-8")
    for name in ("remote.ipynb", "LICENSE", "remote.md"):
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
        )
        try:
            deadline = time.monotonic() + 20
            ready = False
            with httpx.Client(trust_env=False, timeout=0.5) as client:
                while time.monotonic() < deadline:
                    if server.process.poll() is not None:
                        break
                    try:
                        response = client.get(f"{server.url}/api/contents/remote.ipynb")
                        if response.status_code == 200:
                            ready = True
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
            if not ready:
                pytest.fail(f"Jupyverse did not become ready:\n{server.log_path.read_text()}")
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

    def run(*arguments, expected_code=0):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8", NO_COLOR="1", COLUMNS="80")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from jpterm.cli import main; main()",
                "--server",
                jupyverse_server.url,
                "show",
                *arguments,
            ],
            cwd=jupyverse_server.client_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert "WRONG_LOCAL_CONTENT" not in result.stdout + result.stderr
        assert "Traceback" not in result.stderr
        return result

    return run


def test_show_notebook(run_cli, jupyverse_server):
    result = run_cli("remote.ipynb")
    output = result.stdout + result.stderr
    for line in jupyverse_server.source_lines:
        assert output.count(line) == 1
    assert output.count("saved_server_output") == 1
    assert "In [7]" in output
    with httpx.Client(trust_env=False) as client:
        response = client.get(f"{jupyverse_server.url}/api/kernels")
        response.raise_for_status()
        assert response.json() == []


@pytest.mark.parametrize("path", ["remote.ipynb", "LICENSE"])
def test_show_json(run_cli, jupyverse_server, path):
    source = json.loads(run_cli(path, "--json").stdout)
    if path == "LICENSE":
        assert source == jupyverse_server.text
    else:
        cell = source["cells"][0]
        assert cell["id"] == "server-cell"
        assert cell["source"] == jupyverse_server.notebook["cells"][0]["source"]
        assert cell["execution_count"] == 7


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
