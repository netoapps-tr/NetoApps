from __future__ import annotations


class _FakeRoot:
    def __init__(self) -> None:
        self.calls = []

    def state(self, value):
        self.calls.append(("state", value))

    def deiconify(self):
        self.calls.append(("deiconify",))

    def update_idletasks(self):
        self.calls.append(("update_idletasks",))

    def lift(self):
        self.calls.append(("lift",))

    def attributes(self, *args):
        self.calls.append(("attributes", *args))

    def focus_force(self):
        self.calls.append(("focus_force",))


def test_startup_gate_is_skipped_by_default(monkeypatch) -> None:
    import neto_ui

    monkeypatch.delenv("NETO_ENABLE_STARTUP_GATE", raising=False)
    root = _FakeRoot()
    started = []

    result = neto_ui.run_launch_gate(
        root,
        get_asset_path=lambda _name: None,
        veri_yukle=lambda: {"giris_ekrani_atla": False},
        veri_kaydet=lambda _data: None,
        dil_kaydet=lambda _lang: None,
        on_started=started.append,
    )

    assert result is None
    assert started == ["tr"]
    assert ("deiconify",) in root.calls
