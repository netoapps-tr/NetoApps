from __future__ import annotations

import neto_virtual_desktop as virtual_desktop


class FakeManager:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def start(self):
        self.calls.append("start")
        return {"ok": True, "state": "running", "message": "Sanal masaustu baslatildi."}

    def status(self):
        self.calls.append("status")
        return {"ok": True, "state": "running", "message": "Sanal masaustu calisiyor."}

    def stop(self):
        self.calls.append("stop")
        return {"ok": True, "state": "stopped", "message": "Sanal masaustu durduruldu."}

    def restart(self):
        self.calls.append("restart")
        return {"ok": True, "state": "running", "message": "Sanal masaustu yeniden baslatildi."}


def test_virtual_desktop_commands_are_routed_without_ai() -> None:
    manager = FakeManager()

    assert virtual_desktop.handle_command("sanal masaustu baslat", manager=manager)["state"] == "running"
    assert virtual_desktop.handle_command("sanal masaüstü durumu", manager=manager)["state"] == "running"
    assert virtual_desktop.handle_command("sanal masaüstünü durdur", manager=manager)["state"] == "stopped"
    assert virtual_desktop.handle_command("sanal masaustu yeniden baslat", manager=manager)["state"] == "running"
    assert manager.calls == ["start", "status", "stop", "restart"]


def test_unrelated_text_is_not_claimed_by_virtual_desktop() -> None:
    manager = FakeManager()

    assert virtual_desktop.handle_command("merhaba", manager=manager) is None
    assert manager.calls == []

