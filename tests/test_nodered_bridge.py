from __future__ import annotations

from neto_nodered_bridge import NodeRedBridge, _loopback_only


def test_bridge_rejects_remote_urls() -> None:
    assert _loopback_only("http://127.0.0.1:1880")
    assert _loopback_only("http://localhost:1880")
    assert not _loopback_only("https://example.com")

    status = NodeRedBridge("https://example.com").status()
    assert status.available is False
    assert "yerel" in status.message


def test_bridge_rejects_empty_events() -> None:
    result = NodeRedBridge().emit(" ")
    assert result["ok"] is False


def test_operation_loop_events_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("NETOPS_NODERED_EVENTS", "0")
    from neto_operation_loop import _emit_nodered_event

    _emit_nodered_event("netops.test", {"ok": True})
