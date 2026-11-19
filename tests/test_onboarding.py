from __future__ import annotations


def test_onboarding_is_skipped_by_default(monkeypatch) -> None:
    import neto_onboarding

    monkeypatch.delenv("NETO_ENABLE_ONBOARDING", raising=False)
    monkeypatch.delenv("NETO_FORCE_ONBOARDING", raising=False)

    assert neto_onboarding.show_onboarding_if_needed(win=object(), root=object()) is False
