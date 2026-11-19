"""Make bundled PySide6 DLLs discoverable in a frozen Windows build."""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping


_DLL_DIRECTORY_HANDLES: list[object] = []


def configure_qt_dll_path(
    *,
    root: str | None = None,
    environment: MutableMapping[str, str] | None = None,
    platform_name: str | None = None,
) -> None:
    """Prepend both the PyInstaller root and its PySide6 DLL directory."""
    if (platform_name or sys.platform) != "win32":
        return
    bundle_root = str(root or getattr(sys, "_MEIPASS", "")).strip()
    if not bundle_root:
        return
    env = environment if environment is not None else os.environ
    paths = [
        os.path.join(bundle_root, "PySide6"),
        os.path.join(bundle_root, "shiboken6"),
        bundle_root,
    ]
    current = str(env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(path for path in (*paths, current) if path)

    # Python 3.8+ uses the Windows DLL search API for extension modules.  PATH
    # alone is not sufficient when QtCore.pyd is loaded from a frozen bundle.
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        for path in paths:
            if os.path.isdir(path):
                _DLL_DIRECTORY_HANDLES.append(add_dll_directory(path))


if getattr(sys, "frozen", False):
    configure_qt_dll_path()
