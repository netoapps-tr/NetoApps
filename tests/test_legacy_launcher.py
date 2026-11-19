from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_launcher_targets_the_preserved_v142_entrypoint() -> None:
    launcher = (PROJECT_ROOT / "START-NETOPS-LEGACY.ps1").read_text(encoding="utf-8")
    legacy = (
        PROJECT_ROOT
        / "_release_staging_20261024-170109"
        / "NetOps-Zenkamind-Merge-v1.42.0"
        / "asistan beta.py"
    ).read_text(encoding="utf-8-sig")

    assert "NetOps-Zenkamind-Merge-v1.42.0" in launcher
    assert "asistan beta.py" in launcher
    assert "NETOPS_QT_UI" in launcher
    assert "NETOPS_NATIVE_UI_EXPERIMENTAL" in launcher
    assert "_NETOPS_STARTUP_UPDATE_CHECK_ENABLED" in legacy
