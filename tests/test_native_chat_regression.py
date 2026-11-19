import importlib.util
from pathlib import Path


def _load_main_module(monkeypatch):
    monkeypatch.setenv("NETOPS_KEEP_CONSOLE", "1")
    source = Path(__file__).resolve().parents[1] / "asistan beta.py"
    spec = importlib.util.spec_from_file_location("netops_main_chat_regression", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_native_chat_router_answers_before_later_now_playing_setup(monkeypatch):
    module = _load_main_module(monkeypatch)

    result = module.lokal_sistem_islemcisi("merhaba")

    assert "Buraday" in str(result)
