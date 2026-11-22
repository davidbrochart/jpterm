from unittest.mock import Mock

import pytest

from txl.app import AppModule, run


def test_startup_configures_and_runs_fps_directly(monkeypatch):
    module = Mock()
    create = Mock(return_value=module)
    monkeypatch.setattr("txl.app.get_root_module", create)
    options = {
        "backend": "trio",
        "set_": ["cli=false", "remote_contents.url=http://localhost/?key=value"],
        "timeout": 12,
        "stop_timeout": 3,
    }
    run(options)
    create.assert_called_once_with({
        "root_module": {
            "type": AppModule,
            "config": {"cli": "false"},
            "modules": {
                "remote_contents": {"config": {"url": "http://localhost/?key=value"}},
            },
        },
    })
    assert module._global_start_timeout == 12
    assert module._stop_timeout == 3
    module.run.assert_called_once_with(backend="trio")
    assert options["backend"] == "trio"


def test_startup_rejects_invalid_settings_before_running(monkeypatch):
    create = Mock()
    monkeypatch.setattr("txl.app.get_root_module", create)
    with pytest.raises(ValueError, match="No '='"):
        run({"set_": ["invalid"]})
    create.assert_not_called()


@pytest.mark.parametrize("backend", ["asyncio", "trio"])
def test_standalone_startup_stops_services_after_ui_exits(monkeypatch, backend):
    import anyio
    from anytext.app import App
    from fps import Module

    lifecycle = []

    class TestApp(App):
        async def run_async(self, **kwargs):
            lifecycle.append("ui")
            await kwargs["auto_pilot"](None)

    class UiModule(Module):
        async def start(self):
            self.put(TestApp(), App)
            self.done()
            await anyio.sleep_forever()

        async def stop(self):
            lifecycle.append("stop")

    monkeypatch.setattr("txl.app.modules", {"ui": UiModule})
    run({"backend": backend})
    assert lifecycle == ["ui", "stop"]
