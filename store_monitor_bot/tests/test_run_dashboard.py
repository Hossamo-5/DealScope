import runpy
from unittest.mock import MagicMock


def test_run_dashboard_main_executes(monkeypatch):
    run_mock = MagicMock()
    monkeypatch.setattr("uvicorn.run", run_mock)

    runpy.run_module("run_dashboard", run_name="__main__")

    assert run_mock.call_count == 1
    _, kwargs = run_mock.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000


def test_run_dashboard_imports_available():
    import run_dashboard

    assert run_dashboard.app is not None
    assert run_dashboard.uvicorn is not None
