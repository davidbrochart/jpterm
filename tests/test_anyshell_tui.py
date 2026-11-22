"""Exercise real jpterm services inside the existing Anyshell app."""

from pathlib import Path

import anyio
import pytest
from anytext.widgets import Footer
from anytext.widgets._footer import FooterKey
from jpterm.anyshell import register
from txl_jpterm.main import JptermView
from txl_local_kernels.main import LocalKernelsModule
from txl_text_editor.main import TextEditor

shell_api = pytest.importorskip("anyshell")
ui = pytest.importorskip("anyshell.frontend")
pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request):
    return request.param


async def wait_for(check):
    with anyio.fail_after(10):
        while not check():
            await anyio.sleep(0.01)


@pytest.mark.parametrize("exit_key", ["q", "ctrl+q", "cancel"])
async def test_tui_uses_pane_cwd_and_returns_to_prompt(tmp_path, monkeypatch, exit_key):
    cancel = exit_key == "cancel"
    directory = tmp_path / "docs"
    directory.mkdir()
    path = directory / "note.txt"
    path.write_text("original")
    process_cwd = Path.cwd()
    stopped = []
    original_stop = LocalKernelsModule.stop

    async def stop(self):
        await original_stop(self)
        stopped.append(self)

    monkeypatch.setattr(LocalKernelsModule, "stop", stop)
    session = shell_api.Session(shell_api.LocalFileSystem(tmp_path))
    session.cwd = "/docs"
    register(session)
    app = ui.ShellApp(session)

    async with app.run_test(size=(100, 30)) as pilot:
        shell = app.query_one(ui.Shell)
        command = shell.query_one(ui.CommandInput)
        command.value = "jpterm"
        await pilot.press("enter")
        await wait_for(lambda: bool(shell.query(JptermView)) or not shell._busy)
        assert shell.query(JptermView), [e.value for e in shell.output if e.kind == "error"]
        view = shell.query_one(JptermView)
        await wait_for(lambda: view.launcher.is_mounted)
        await wait_for(lambda: view.has_focus_within)
        await pilot.pause()
        assert view.app is app
        assert view.header.screen_title == "jpterm"
        assert view.header.screen_sub_title == ""
        assert app.title == "Anyshell"
        assert len(app.query(Footer)) == 2
        assert view.footer.is_mounted
        await pilot.pause()
        global_footer = next(footer for footer in app.query(Footer) if footer is not view.footer)
        assert global_footer.display and view.footer.display
        await wait_for(lambda: "q" in {key.key for key in view.footer.query(FooterKey)})
        local_keys = {key.key for key in view.footer.query(FooterKey)}
        global_keys = {key.key for key in global_footer.query(FooterKey)}
        assert "q" in local_keys and "alt+v" not in local_keys
        assert "alt+v" in global_keys and "q" not in global_keys
        assert not hasattr(app, "cli")
        await view.file_browser.open_file_signal.emit(str(path))
        await pilot.pause()
        editor = view.query_one(TextEditor)
        assert editor.editor.text == "original"
        if cancel:
            shell.cancel()
        else:
            editor.editor.focus()
            await pilot.press("end", "!", "ctrl+s")
            await pilot.pause()
            assert path.read_text() == "original!"
            if exit_key == "q":
                await pilot.press("ctrl+w")
                await pilot.pause()
                view.launcher.focus()
            # Ctrl+Q must also work from inside the text editor, without
            # reaching the host app's global quit action.
            await pilot.press(exit_key)
        await wait_for(lambda: not shell._busy)
        assert not shell.query(JptermView)
        assert session.last_status == (130 if cancel else 0), [
            e.value for e in shell.output if e.kind == "error"
        ]
        await wait_for(lambda: command.has_focus)
        assert app.is_running
        assert len(stopped) == 1
        assert Path.cwd() == process_cwd
        command.value = "echo restored"
        await pilot.press("enter")
        await wait_for(lambda: not shell._busy)
        assert any(e.kind == "output" and e.value == "restored" for e in shell.output)


async def test_closing_pane_stops_embedded_tui(tmp_path):
    session = shell_api.Session(shell_api.LocalFileSystem(tmp_path))
    register(session)
    app = ui.ShellApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        workspace = app.query_one("ShellWorkspace")
        original = workspace.active
        await pilot.press("alt+v")
        closing = workspace.active
        closing.query_one(ui.CommandInput).value = "jpterm"
        await pilot.press("enter")
        await wait_for(lambda: bool(closing.query(JptermView)))
        view = closing.query_one(JptermView)
        await pilot.pause()
        await pilot.press("alt+w")
        await wait_for(lambda: not closing._busy)
        assert view.closed.is_set()
        assert workspace.panes == [original]
        await wait_for(lambda: original.query_one(ui.CommandInput).has_focus)
        assert app.is_running
