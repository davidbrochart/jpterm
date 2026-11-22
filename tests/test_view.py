from anyio import fail_after, run, sleep
from anytext.app import App
from anytext.containers import Horizontal, Vertical
from anytext.widgets import Button, Footer, Static
from txl_jpterm.main import Jpterm, JptermView
from txl_jpterm.main_area import MainArea


def make_view():
    header, footer = Static("Header"), Static("Footer")
    area = MainArea()
    launcher = Button("Launcher")
    browser = Static("Files", id="browser-view")
    view = JptermView(header, footer, area)
    view.start(launcher, browser)
    return view


def test_view_mounts_all_components_and_scopes_its_styles():
    async def check():
        view = make_view()
        unrelated_browser = Static("Host content", id="browser-view")

        class Host(App):
            def compose(self):
                yield Horizontal(view, Vertical(unrelated_browser))

        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not hasattr(app, "cli")
            assert view.header.is_mounted and view.footer.is_mounted
            assert view.file_browser.is_mounted and view.launcher.is_mounted
            assert view.main_area.shown is view.launcher
            assert view.file_browser.display
            assert unrelated_browser.display
            view.action_toggle_files()
            await pilot.pause()
            assert not view.file_browser.display
            assert unrelated_browser.display
            view.action_toggle_files()
            await pilot.pause()
            assert view.file_browser.display

    run(check)


def test_quitting_an_embedded_view_does_not_exit_the_host():
    async def check():
        view = make_view()

        class Host(App):
            def compose(self):
                yield view

        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            view.launcher.focus()
            await pilot.press("q")
            assert view.closed.is_set()
            assert app.is_running
            await view.remove()
            assert app.is_running

    run(check)


def test_standalone_app_exits_when_its_view_closes():
    async def check():
        area = MainArea()
        app = Jpterm(Static(), Static(), area)
        app.start(Button("Launcher"), Static())
        async with app.run_test() as pilot:
            await pilot.pause()
            app.view.launcher.focus()
            await pilot.press("q")
            with fail_after(2):
                while app.is_running:
                    await sleep(0.01)

    run(check)


def test_two_views_keep_actions_and_browser_visibility_independent():
    async def check():
        first, second = make_view(), make_view()

        class Host(App):
            def compose(self):
                yield Horizontal(first, second)

        app = Host()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            first.launcher.focus()
            await pilot.press("f")
            assert not first.file_browser.display
            assert second.file_browser.display
            second.launcher.focus()
            await pilot.press("f")
            assert not first.file_browser.display
            assert not second.file_browser.display
            await pilot.press("q")
            assert second.closed.is_set()
            assert not first.closed.is_set()
            assert app.is_running

    run(check)


def test_removing_view_dismisses_its_unsaved_changes_dialog():
    from txl_jpterm.close_tab import ConfirmCloseTab

    async def check():
        view = make_view()

        class Host(App):
            def compose(self):
                yield view

        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            document = Button("Dirty document")
            view.main_area.show(document, "Dirty")
            await pilot.pause()
            view.main_area.set_dirty(document)
            await view.action_close_tab()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmCloseTab)
            await view.remove()
            await pilot.pause()
            assert not isinstance(app.screen, ConfirmCloseTab)
            assert view.closed.is_set()
            assert app.is_running

    run(check)


def test_view_keeps_its_footer_when_host_has_one():
    async def check():
        view = make_view()
        view.footer = Footer()

        class Host(App):
            def compose(self):
                yield view
                yield Footer()

        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert len(app.query(Footer)) == 2
            assert view.footer.is_mounted
            assert view.launcher.is_mounted

    run(check)


def test_standalone_view_keeps_its_own_footer():
    async def check():
        area = MainArea()
        footer = Footer()
        app = Jpterm(Static(), footer, area)
        app.start(Button("Launcher"), Static())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert footer.is_mounted
            assert len(app.query(Footer)) == 1

    run(check)
