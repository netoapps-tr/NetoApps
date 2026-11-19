from pathlib import Path


def test_qt_cover_loader_reads_image_by_content():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "netops_qt_shell.py").read_text(encoding="utf-8")

    assert "def load_cover_pixmap(path: str) -> QPixmap:" in source
    assert "QImageReader(candidate)" in source
    assert "load_cover_pixmap(cover_path)" in source


def test_qt_runtime_hook_prepends_bundled_pyside_path():
    import importlib.util

    project_root = Path(__file__).resolve().parents[1]
    hook_path = project_root / "runtime_hooks" / "netops_qt_path.py"
    spec = importlib.util.spec_from_file_location("netops_qt_path_test", hook_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    environment = {"PATH": "existing-path"}
    module.configure_qt_dll_path(
        root=r"C:\bundle",
        environment=environment,
        platform_name="win32",
    )

    assert environment["PATH"].split(";")[:3] == [
        r"C:\bundle\PySide6",
        r"C:\bundle\shiboken6",
        r"C:\bundle",
    ]


def test_spec_places_shiboken_runtime_next_to_pyside_extensions():
    project_root = Path(__file__).resolve().parents[1]
    spec_source = (project_root / "NetOps.spec").read_text(encoding="utf-8")

    assert "shiboken6.abi3.dll" in spec_source
    assert "binaries.append" in spec_source
    assert '"PySide6"' in spec_source


def test_spec_places_icu_runtime_next_to_pyside_extensions():
    project_root = Path(__file__).resolve().parents[1]
    spec_source = (project_root / "NetOps.spec").read_text(encoding="utf-8")

    assert "windows_icu_dir" in spec_source
    assert '"icu.dll"' in spec_source
    assert '"icuuc.dll"' in spec_source
    assert '"PySide6"' in spec_source


def test_spec_collects_winrt_projection_runtime_files():
    project_root = Path(__file__).resolve().parents[1]
    spec_source = (project_root / "NetOps.spec").read_text(encoding="utf-8")

    assert "collect_all('winrt')" in spec_source or 'collect_all("winrt")' in spec_source
