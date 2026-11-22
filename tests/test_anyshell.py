from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

shell = pytest.importorskip("anyshell")
jpterm = pytest.importorskip("jpterm.anyshell")
LocalFileSystem = shell.LocalFileSystem
Session = shell.Session

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    api = SimpleNamespace(
        load=AsyncMock(return_value="first\nsecond\n"),
        write=AsyncMock(),
        execute=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr("jpterm.show.load_document", api.load)
    monkeypatch.setattr("jpterm.write.write_document", api.write)
    monkeypatch.setattr("jpterm.execute.execute_notebook", api.execute)
    session = Session(LocalFileSystem(tmp_path))
    jpterm.register(session)
    return session, api


async def run(session, command, *, is_terminal=False):
    events = []

    async def emit(event):
        events.append(event)

    result = await session.execute(command, emit, is_terminal=is_terminal)
    return (
        result.status,
        [event.value for event in events if event.kind == "output"],
        events,
    )


async def test_show_uses_pane_cwd_and_pipeline(adapter, tmp_path):
    session, api = adapter
    (tmp_path / "docs").mkdir()
    before = Path.cwd()
    await run(session, "cd docs")
    status, output, _ = await run(session, "jpterm show note.txt | grep second")
    assert status == 0
    assert output == ["second"]
    api.load.assert_awaited_once_with(
        str(tmp_path / "docs/note.txt"),
        [],
        30,
        False,
        None,
        False,
        return_renderable=False,
        width=88,
    )
    assert Path.cwd() == before


async def test_notebook_capture(adapter):
    session, api = adapter
    api.load.return_value = {"cells": []}
    assert (await run(session, "data = jpterm show notebook.ipynb"))[0] == 0
    assert session.variables["data"] == [{"cells": []}]


async def test_terminal_uses_jpterms_rendering(adapter, tmp_path):
    from rich.text import Text

    session, api = adapter
    api.load.return_value = Text("print(42)", style="green")
    status, output, _ = await run(session, "jpterm show example.py", is_terminal=True)
    assert status == 0
    assert output == [api.load.return_value]
    api.load.assert_awaited_once_with(
        str(tmp_path / "example.py"),
        [],
        30,
        True,
        None,
        False,
        return_renderable=True,
        width=88,
    )


async def test_write_pipeline(adapter, tmp_path):
    session, api = adapter
    status, _, _ = await run(session, "echo hello | jpterm write note.txt --stdin")
    assert status == 0
    api.write.assert_awaited_once_with(str(tmp_path / "note.txt"), "hello", None, [], 30, False)


async def test_write_empty_cell(adapter, tmp_path):
    session, api = adapter
    status, _, _ = await run(session, "jpterm write n.ipynb --cell abc --source ''")
    assert status == 0
    api.write.assert_awaited_once_with(str(tmp_path / "n.ipynb"), "", "abc", [], 30, False)


@pytest.mark.parametrize(
    "command",
    [
        "jpterm write n.txt",
        "jpterm write n.txt --source x --stdin",
        "jpterm show n.txt --source x",
        "jpterm show n.txt --kernel python3",
        "jpterm show n.txt --timeout 0",
        "jpterm show n.txt --timeout nan",
    ],
)
async def test_invalid_options(adapter, command):
    session, api = adapter
    assert (await run(session, command))[0] == 1
    api.load.assert_not_awaited()
    api.write.assert_not_awaited()


async def test_execute_reports_cell_error_after_output(adapter):
    session, api = adapter
    api.execute.return_value = [{"ename": "ValueError", "evalue": "bad cell"}]
    api.load.return_value = {"cells": []}
    status, output, events = await run(session, "jpterm execute n.ipynb --kernel python3")
    assert status == 1
    assert output == [{"cells": []}]
    assert any(event.value == "jpterm: ValueError: bad cell" for event in events)


async def test_plugin_errors_are_unwrapped(adapter):
    session, api = adapter
    api.load.side_effect = ExceptionGroup("plugins", [FileNotFoundError("missing")])
    status, _, events = await run(session, "jpterm show missing")
    assert status == 1
    assert any(event.value == "jpterm: missing" for event in events)


@pytest.mark.parametrize("wrapped", [False, True])
async def test_timeout_has_useful_message(adapter, wrapped):
    session, api = adapter
    error = TimeoutError()
    api.load.side_effect = ExceptionGroup("plugins", [error]) if wrapped else error
    status, _, events = await run(session, "jpterm show slow.txt")
    assert status == 1
    assert any(event.value == "jpterm: Timed out loading document" for event in events)


async def test_rejects_memory_filesystem(adapter):
    _, api = adapter
    session = Session()
    jpterm.register(session)
    assert (await run(session, "jpterm show n.txt"))[0] == 1
    api.load.assert_not_awaited()


async def test_rejects_symlink_outside_workspace(adapter, tmp_path):
    session, api = adapter
    (tmp_path / "outside").symlink_to(tmp_path.parent, target_is_directory=True)
    assert (await run(session, "jpterm show outside/secret"))[0] == 1
    api.load.assert_not_awaited()


def test_registers_the_same_tree_as_standalone_cli(adapter):
    from jpterm.cli import app

    session, _ = adapter
    assert session.commands["jpterm"]._parser is app.meta


async def test_shared_kernel_subcommands_and_options(adapter, monkeypatch):
    session, _ = adapter
    records = [{"path": "notebook.ipynb", "kernel_name": "python3", "pid": 123, "alive": True}]
    monkeypatch.setattr("jpterm.kernel.list_sessions", lambda: records)
    status, output, _ = await run(session, "jpterm kernel list | select kernel_name")
    assert status == 0
    assert output == ["python3"]
    assert await session.complete("jpterm kernel st") == [
        "jpterm kernel start ",
        "jpterm kernel stop ",
    ]


async def test_root_options_and_remote_paths(adapter):
    session, api = adapter
    api.load.return_value = {"cells": []}
    status, output, _ = await run(session, "jpterm --server http://example.test show note.ipynb")
    assert status == 0
    assert output == [{"cells": []}]
    assert api.load.call_args.args[0] == "note.ipynb"
    assert "remote_contents.url=http://example.test" in api.load.call_args.args[1]


async def test_help_uses_the_shared_tree(adapter, capsys):
    session, _ = adapter
    status, output, _ = await run(session, "jpterm show --help")
    assert status == 0
    text = "\n".join(output)
    assert "--show-cell-ids" in text
    assert "--source" not in text
    assert capsys.readouterr().out == ""


async def test_repeated_configuration_options_are_shared(adapter):
    session, api = adapter
    status, _, _ = await run(
        session, "jpterm --set text_editor.register=false --set custom.value=2 show note.txt"
    )
    assert status == 0
    assert api.load.call_args.args[1] == ["text_editor.register=false", "custom.value=2"]
