from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import pytest
from jupyter_ydoc import YFile
from textual.widgets import Button, Static, Tab
from txl_jpterm.close_tab import ConfirmCloseTab
from txl_jpterm.main import Jpterm
from txl_jpterm.main_area import MainArea
from txl_text_editor.main import TextEditor


def make_app():
    area = MainArea()
    launcher = Button("Launcher", id="test-launcher")
    app = Jpterm(Static(), Static(), area)
    app.start(launcher, Static())
    return app, area, launcher


def test_close_tabs_selects_neighbour_and_restores_launcher():
    async def check():
        app, area, launcher = make_app()
        first, second = Button("First"), Button("Second")
        async with app.run_test() as pilot:
            await pilot.pause()
            area.show(first, "First")
            await pilot.pause()
            area.show(second, "Second")
            await pilot.pause()
            assert area.shown is second
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert area.shown is first
            assert first.has_focus
            assert second not in area.mounted
            assert second.parent is None
            area.show(launcher)
            await pilot.pause()
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert area.shown is first
            assert launcher not in area.widget_to_tab
            await pilot.press("ctrl+w")
            await pilot.pause()
            assert area.shown is launcher
            assert launcher.has_focus
            assert area.mounted == [launcher]
            assert len(area.tabs.query(Tab)) == 1
            await pilot.press("ctrl+w", "l")
            await pilot.pause()
            assert area.mounted == [launcher]
            assert len(area.tabs.query(Tab)) == 1
            # New documents can still be opened after all document tabs close.
            third = Button("Third")
            area.show(third, "Third")
            await pilot.pause()
            assert area.shown is third

    anyio.run(check)


@pytest.mark.parametrize("close_action", ["discard", "save"])
@pytest.mark.parametrize("size", [(80, 24), (40, 18)])
def test_close_modified_editor_requires_confirmation_and_cleans_up(close_action, size):
    async def check():
        async with anyio.create_task_group() as tasks:
            app, area, launcher = make_app()
            document = YFile()
            document.source = "original"
            contents = SimpleNamespace(get=AsyncMock(return_value=document), save=AsyncMock())
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                editor = TextEditor(contents, area, tasks)
                area.show(editor, "example.txt")
                await editor.open("example.txt")
                await pilot.pause()
                editor.editor.focus()
                document._ysource += " changed"
                await pilot.pause()
                assert area.widget_to_tab[editor][1]
                await pilot.press("ctrl+w")
                assert isinstance(app.screen, ConfirmCloseTab)
                await pilot.press("escape")
                await pilot.pause()
                assert area.shown is editor
                assert document.source == "original changed"
                contents.save.assert_not_awaited()
                if close_action == "discard":
                    await pilot.press("ctrl+w")
                    await pilot.click("#discard-changes")
                else:
                    await pilot.press("ctrl+s")
                    await pilot.pause()
                    contents.save.assert_awaited_once_with("example.txt", document)
                    assert not area.widget_to_tab[editor][1]
                    await pilot.press("ctrl+w")
                await pilot.pause()
                assert not isinstance(app.screen, ConfirmCloseTab)
                assert area.shown is launcher
                assert editor not in area.widget_to_tab
                assert editor.parent is None
                assert editor._closed
                # Later shared-document changes must not reach a closed TextInput.
                document._ysource += " after close"
                await pilot.pause()
                await editor.close()  # Application shutdown can close it again safely.
            tasks.cancel_scope.cancel()

    anyio.run(check)
