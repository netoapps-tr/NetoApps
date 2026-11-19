from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_logo_intro_accepts_live_startup_status_provider() -> None:
    source = (PROJECT_ROOT / "neto_ui.py").read_text(encoding="utf-8")

    assert "startup_status_provider=None" in source
    assert "startup_status_provider" in source
    assert "devices_var" in source


def test_main_launch_passes_netops_startup_status_provider() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")

    assert "startup_status_provider=neto_startup_status_snapshot" in source
    assert "def neto_startup_status_snapshot" in source


def test_main_launch_has_a_direct_start_branch_for_v1_50() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")

    assert "NETOPS_DIRECT_START" in source
    assert "_neto_launch_started" in source


def test_legacy_launch_checks_for_updates_by_default() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")

    assert "_NETOPS_STARTUP_UPDATE_CHECK_ENABLED" in source
    assert 'os.environ.get("NETO_ENABLE_STARTUP_UPDATE_CHECK", "1")' in source


def test_direct_start_restores_and_focuses_borderless_window() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")
    direct_branch = source.split("if NETOPS_DIRECT_START:", 1)[1].split("else:", 1)[0]

    assert "root.update_idletasks()" in direct_branch
    assert "root.lift()" in direct_branch
    assert "root.focus_force()" in direct_branch
    assert 'root.attributes("-topmost", True)' in direct_branch


def test_direct_start_maps_window_after_mainloop_begins() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")
    direct_branch = source.split("if NETOPS_DIRECT_START:", 1)[1].split("else:", 1)[0]

    assert "def _neto_direct_start()" in direct_branch
    assert "root.after(0, _neto_direct_start)" in direct_branch
