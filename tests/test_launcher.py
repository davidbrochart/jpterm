"""FPS services and the UI run in sibling tasks with distinct task contexts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio
from anytext.app import App
from anytext.widgets import Button, Static
from fps import Module, get_root_module
from txl_jpterm.main import Jpterm, JptermModule
from txl_launcher.main import LauncherModule

from txl.app import AppModule
from txl.base import Editors, FileBrowser, Launcher


def test_service_can_register_a_launcher_document_after_mount():
    class HeadlessJpterm(Jpterm):
        async def run_async(self, **kwargs):
            kwargs.update(headless=True, size=(80, 24))
            return await super().run_async(**kwargs)

    class Services(Module):
        async def start(self):
            browser = Static()
            browser.open_file_signal = SimpleNamespace(connect=lambda callback: None)
            self.put(browser, FileBrowser)
            self.put(SimpleNamespace(on_open=AsyncMock()), Editors)

    class LateDocument(Module):
        async def start(self):
            launcher = await self.get(Launcher)
            with anyio.fail_after(3):
                while not launcher.is_mounted:
                    await anyio.sleep(0.01)
            # This is an FPS service task, not a task started by Anytext.
            launcher.register("late-notebook", lambda: None)

    async def check():
        root = get_root_module({"app": {"type": AppModule}})
        root._global_start_timeout = 5
        with anyio.fail_after(10):
            async with root:
                application = await root.get(App)
                launcher = await root.get(Launcher)
                with anyio.fail_after(3):
                    while not launcher.query("#late-notebook"):
                        await anyio.sleep(0.01)
                button = launcher.query_one("#late-notebook", Button)
                await button._mounted_event.wait()
                assert application.is_running
                assert application.view.launcher is launcher
                application.view.action_close()
                await root.app_exited.wait()
        assert not root._exceptions

    registered = {
        "jpterm": JptermModule,
        "launcher": LauncherModule,
        "services": Services,
        "late_document": LateDocument,
    }
    with patch("txl.app.modules", registered), patch("txl_jpterm.main.Jpterm", HeadlessJpterm):
        anyio.run(check)
