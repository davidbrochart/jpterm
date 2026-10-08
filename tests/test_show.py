import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import anyio
import httpx
from click.testing import CliRunner
from fps import Module, get_root_module
from jpterm.cli import main
from jpterm.show import load_document
from pycrdt import YMessageType, YSyncMessageType
from rich.console import Console
from textual.app import App
from textual.widgets import Static
from txl_editors.main import _Editors
from txl_jpterm.main import Jpterm
from txl_jpterm.main_area import MainArea
from txl_markdown_viewer.main import MarkdownViewer, MarkdownViewerModule
from txl_notebook_editor.main import NotebookEditor, NotebookEditorModule
from txl_remote_contents.main import RemoteContents, SyncedWebsocket, ydocs
from txl_text_editor.main import TextEditor, TextEditorModule

from txl.app import AppModule
from txl.base import CellFactory, Contents, Editors, Kernels, Kernelspecs, Launcher
from txl.base import MainArea as MainAreaService


def test_ctrl_q_exits_application_and_stops_plugins():

    class TestApp(App):
        async def run_async(self, **kwargs):
            ready = kwargs["auto_pilot"]

            async def quit(pilot):
                await ready(pilot)
                await pilot.press("ctrl+q")

            kwargs.update(headless=True, auto_pilot=quit)
            return await super().run_async(**kwargs)

    class TestModule(Module):
        async def start(self):
            self.put(TestApp(), App)
            self.done()
            await anyio.sleep_forever()

        async def stop(self):
            stopped.append(True)

    stopped = []

    async def check():
        root = get_root_module({"app": {"type": AppModule}})
        with anyio.fail_after(3):
            await root._main()
        assert root.app_exited.is_set()
        assert stopped

    with patch("txl.app.modules", {"test": TestModule}):
        anyio.run(check)


def test_inline_uses_text_editor_for_text_file():
    lines = [f"text_line_{index:02}" for index in range(50)]
    app, contents = render_file("\n".join(lines), "example.txt", TextEditorModule, TextEditor)
    assert app.read_only
    contents.get.assert_awaited_once_with("example.txt", type="file")
    for line in lines:
        assert app.output.count(line) == 1


def test_extensionless_file_falls_back_to_plain_text():
    app, contents = render_file(
        "MIT License\n\nCopyright example\n", "LICENSE", TextEditorModule, TextEditor
    )
    assert app.output.count("MIT License") == 1
    assert "Copyright example" in app.output
    assert [line.rstrip() for line in app.output.splitlines()] == [
        "MIT License",
        "",
        "Copyright example",
    ]
    contents.get.assert_awaited_once_with("LICENSE", type="file")
    assert contents.get.return_value.source == "MIT License\n\nCopyright example\n"


def test_inline_renders_markdown_to_end():
    source = (
        "# First heading\n\n"
        + "\n\n".join((f"Paragraph {index:02}" for index in range(30)))
        + "\n\n## Last heading\n\n| Name | Value |\n| --- | --- |\n| final_row | 42 |\n"
    )
    app, _ = render_file(source, "example.md", MarkdownViewerModule, MarkdownViewer)
    assert app.read_only
    for text in ("First heading", "Paragraph 29", "Last heading", "final_row", "42"):
        assert app.output.count(text) == 1


def test_markdown_preserves_block_spacing():
    app, _ = render_file(
        "# Heading\n\nParagraph\n", "example.md", MarkdownViewerModule, MarkdownViewer
    )
    lines = [line.strip() for line in app.output.splitlines()]
    assert lines == ["", "", "Heading", "", "Paragraph", ""]


def render_file(source, path, module_type, editor_type):
    document = ydocs["file"]()
    document.source = source
    contents = SimpleNamespace(get=AsyncMock(return_value=document))

    class TestApp(App):
        async def run_async(self, **kwargs):
            self.requested_headless = kwargs["headless"]
            kwargs.update(headless=True, inline=False, size=(80, 10))
            return await super().run_async(**kwargs)

        def exit(self, *args, **kwargs):
            editor = self.query_one(editor_type)
            self.read_only = editor.read_only
            output = StringIO()
            Console(file=output, width=80).print(kwargs.pop("message"))
            self.output = output.getvalue()
            return super().exit(*args, **kwargs)

    app = TestApp()

    class TestModule(Module):
        async def start(self):
            main_area = MainArea()
            self.put(contents, Contents)
            self.put(app, App)
            self.put(main_area, MainAreaService)
            self.put(_Editors(Static(), Static(), main_area), Editors)

    with patch("txl.app.modules", {"test": TestModule, "viewer": module_type}):
        anyio.run(load_document, path, [], 5, True)
    assert app.requested_headless
    return (app, contents)


def test_tui_mounts_application_shell():

    async def check():
        header, footer, browser, launcher = [Static() for _ in range(4)]
        main_area = MainArea()
        app = Jpterm(header, footer, main_area)
        app.start(launcher, browser)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert header.is_mounted
            assert footer.is_mounted
            assert browser.is_mounted
            assert launcher.is_mounted

    anyio.run(check)


def test_cli_does_not_start_application_shell():

    async def check():
        app = Jpterm(Static(), Static(), Static())
        app.cli = True
        async with app.run_test():
            assert len(app.screen.children) == 0

    anyio.run(check)


def test_inline_uses_notebook_editor_without_starting_kernel():
    sources = [f"source_{index:02}" for index in range(30)]
    sources[0] = "\n".join((f"long_line_{index:02}" for index in range(40)))
    notebook = {"cells": [], "metadata": {"kernelspec": {"name": "python3"}}}
    document = SimpleNamespace(
        source=notebook, ycells=sources, cell_number=len(sources), observe=lambda callback: None
    )
    contents = SimpleNamespace(get=AsyncMock(return_value=document))
    used_cells = []
    kernels = Mock()
    kernelspecs = SimpleNamespace(get=AsyncMock())

    class TestApp(App):
        async def run_async(self, **kwargs):
            self.inline_requested = kwargs["inline"]
            kwargs.update(headless=True, inline=False, size=(80, 10))
            return await super().run_async(**kwargs)

        def exit(self, *args, **kwargs):
            self.rendered = self.query_one(NotebookEditor).size.height > 0
            output = StringIO()
            Console(file=output, width=80).print(kwargs.pop("message"))
            self.output = output.getvalue()
            self.final_height = self.screen.size.height
            return super().exit(*args, **kwargs)

    app = TestApp()

    def factory(cell, language, kernel):
        assert kernel is None
        used_cells.append(cell)
        widget = Static(cell)
        widget.source = widget
        widget.select = lambda: None
        return widget

    class TestModule(Module):
        async def start(self):
            self.put(contents, Contents)
            self.put(app, App)
            self.put(factory, CellFactory)
            self.put(kernels, Kernels)
            self.put(kernelspecs, Kernelspecs)
            self.put(SimpleNamespace(register=Mock()), Launcher)
            main_area = MainArea()
            self.put(main_area, MainAreaService)
            self.put(_Editors(Static(), Static(), main_area), Editors)

    with patch("txl.app.modules", {"test": TestModule, "notebook_editor": NotebookEditorModule}):
        anyio.run(load_document, "example.ipynb", [], 1, True)
    assert app.inline_requested
    assert used_cells == sources
    assert app.rendered
    assert app.final_height > 40
    for source in sources:
        for line in source.splitlines():
            assert app.output.count(line) == 1
    kernels.assert_not_called()
    kernelspecs.get.assert_not_awaited()
    contents.get.assert_awaited_once_with("example.ipynb", type="notebook", format="json")


def test_collaborative_get_waits_for_sync():

    async def check():
        provider_started = anyio.Event()
        allow_sync = anyio.Event()
        returned = anyio.Event()
        response = httpx.Response(
            200,
            request=httpx.Request("PUT", "http://server/api/collaboration/session/test"),
            json={"format": "json", "type": "notebook", "fileId": "test", "sessionId": "session"},
        )
        client = AsyncMock()
        client.put.return_value = response
        client.__aenter__.return_value = client
        async with anyio.create_task_group() as tasks:
            contents = RemoteContents("http://server", {}, httpx.Cookies(), True, tasks)

            async def provider(room, document, session, synced):
                provider_started.set()
                await allow_sync.wait()
                synced.set()

            contents.websocket_provider = provider

            async def load():
                await contents.get("test", type="notebook")
                returned.set()

            with patch("txl_remote_contents.main.httpx.AsyncClient", return_value=client):
                tasks.start_soon(load)
                await provider_started.wait()
                assert not returned.is_set()
                allow_sync.set()
                await returned.wait()

    anyio.run(check)


def test_load_uses_injected_contents():
    notebook = {"cells": []}
    contents = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(source=notebook)))

    class TestContentsModule(Module):
        async def start(self):
            self.put(contents, Contents)
            self.put(App(), App)

    with patch("txl.app.modules", {"test_contents": TestContentsModule}):
        result = anyio.run(load_document, "example.ipynb", [], 5)
    assert result == notebook
    contents.get.assert_awaited_once_with("example.ipynb", type="notebook")


def invoke(args):
    with patch("sys.argv", ["jpterm", *args]):
        with CliRunner().isolation() as output:
            try:
                main()
            except SystemExit as exc:
                code = exc.code
            else:
                code = 0
        return (code, output[0].getvalue().decode() + output[1].getvalue().decode())


def test_json_and_inline():
    notebook = {
        "cells": [
            {
                "id": "abc",
                "cell_type": "code",
                "source": ["print(1)"],
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "text": ["1\n"]}],
            }
        ]
    }
    with patch("jpterm.show.load_document", AsyncMock(return_value=notebook)) as load:
        code, output = invoke(["show", "example.ipynb", "--json"])
        assert code == 0
        assert json.loads(output) == notebook
        assert not load.call_args.args[-1]
        code, output = invoke(["show", "example.ipynb"])
        assert code == 0
        assert load.call_args.args[-1]


def test_tui_default():
    with patch("txl.cli.run") as run:
        code, _ = invoke([])
        assert code == 0
        run.assert_called_once()


def test_error():
    with patch("jpterm.show.load_document", AsyncMock(side_effect=ValueError("bad notebook"))):
        code, _ = invoke(["show", "bad.ipynb"])
        assert code == 1


def test_sync_signal_follows_application():

    async def check():
        synced = anyio.Event()
        websocket = AsyncMock()
        websocket.receive_bytes.side_effect = [
            bytes([YMessageType.SYNC, YSyncMessageType.SYNC_STEP2]),
            b"next",
        ]
        channel = SyncedWebsocket(websocket, "room", synced)
        await channel.__anext__()
        assert not synced.is_set()
        await channel.__anext__()
        assert synced.is_set()

    anyio.run(check)
