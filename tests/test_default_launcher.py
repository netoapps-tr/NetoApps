from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_default_batch_launcher_selects_the_new_native_ui() -> None:
    source = (PROJECT_ROOT / "ARKADAS_BASLAT.bat").read_text(encoding="utf-8-sig")

    assert 'set "NETOPS_QT_UI=1"' in source
    assert 'set "NETOPS_LEGACY_UI=0"' in source
    assert 'set "NETOPS_NATIVE_UI_EXPERIMENTAL=1"' in source
    assert 'set "PY=py -3.12"' in source
    assert '%PY% "asistan beta.py"' in source


def test_powershell_launcher_prefers_the_installed_python_312_runtime() -> None:
    source = (PROJECT_ROOT / "START-NETOPS.ps1").read_text(encoding="utf-8")

    assert "Python312\\python.exe" in source
    assert "-3.12 -c" in source
