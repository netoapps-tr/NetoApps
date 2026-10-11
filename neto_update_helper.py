"""Safe Windows update installer helpers for NetOps."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, List


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def current_command(extra_args: Iterable[str] = ()) -> List[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        launcher = app_root() / "asistan beta.py"
        command = [sys.executable, str(launcher)]
    command.extend(str(value) for value in extra_args)
    return command


def _version_from_tag(tag: str) -> str:
    match = re.search(r"\d+(?:\.\d+)+", str(tag or ""))
    return match.group(0) if match else ""


def _quote_bat(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for info in archive.infolist():
        raw = str(info.filename or "").replace("\\", "/")
        if not raw or raw.endswith("/"):
            continue
        parts = [part for part in raw.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise RuntimeError(f"Güvensiz ZIP yolu engellendi: {raw}")
        # Unix symlink bit. ZIP updates must contain normal files/directories only.
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise RuntimeError(f"Sembolik bağlantı engellendi: {raw}")
        target = destination.joinpath(*parts).resolve()
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise RuntimeError(f"ZIP yolu hedef dışına çıkıyor: {raw}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info, "r") as source, target.open("wb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)


def _zip_update_script(zip_path: Path, restart: bool, release_id: Any = None, tag: str = "") -> Path:
    root = app_root()
    staging = Path(tempfile.mkdtemp(prefix="neto_update_stage_"))
    with zipfile.ZipFile(zip_path, "r") as archive:
        _safe_extract(archive, staging)

    children = list(staging.iterdir())
    source = children[0] if len(children) == 1 and children[0].is_dir() else staging
    script = Path(tempfile.gettempdir()) / f"neto_apply_update_{os.getpid()}.bat"
    log_path = Path(tempfile.gettempdir()) / "neto_update_install.log"
    restart_cmd = current_command(
        [
            f"--neto-updated-release-id={release_id or ''}",
            f"--neto-updated-tag={tag or ''}",
        ]
    )
    restart_line = "start \"\" " + " ".join(_quote_bat(value) for value in restart_cmd) if restart else ""
    installed_version = _version_from_tag(tag)
    version_line = (
        f'> {_quote_bat(str(root / "APP_VERSION.txt"))} echo {installed_version}'
        if installed_version
        else ""
    )
    content = f"""@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "NETO_LOG={str(log_path)}"
echo [%date% %time%] Neto update started>"%NETO_LOG%"
ping 127.0.0.1 -n 5 >nul
robocopy {_quote_bat(str(source))} {_quote_bat(str(root))} /E /IS /IT /R:5 /W:1 /NFL /NDL /NJH /NJS >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] Robocopy exit code: %RC%>>"%NETO_LOG%"
if %RC% GEQ 8 goto COPY_FAILED
{version_line}
{restart_line}
goto CLEANUP
:COPY_FAILED
echo [%date% %time%] Update copy failed.>>"%NETO_LOG%"
start "" notepad "%NETO_LOG%"
:CLEANUP
rmdir /s /q {_quote_bat(str(staging))} >nul 2>&1
del "%~f0"
"""
    script.write_text(content, encoding="utf-8-sig")
    return script


def install_update(
    path: str,
    restart: bool = True,
    release_id: Any = None,
    tag: str = "",
    **_: Any,
) -> dict:
    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    suffix = target.suffix.lower()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    if suffix == ".zip":
        if os.name != "nt":
            raise RuntimeError("Otomatik ZIP kurulumu şu anda Windows için tasarlandı.")
        script = _zip_update_script(target, restart=restart, release_id=release_id, tag=tag)
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(script)],
            cwd=str(app_root()),
            creationflags=creation_flags,
        )
        return {"ok": True, "mode": "zip", "script": str(script), "requires_exit": True}
    if suffix in {".exe", ".msi"}:
        command = [str(target)] if suffix == ".exe" else ["msiexec", "/i", str(target)]
        subprocess.Popen(command, cwd=str(target.parent), creationflags=creation_flags)
        return {"ok": True, "mode": "installer", "requires_exit": True}
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(target)], creationflags=creation_flags)
    return {"ok": False, "mode": "unsupported", "path": str(target), "requires_exit": False}


def apply_update(*args: Any, **kwargs: Any) -> dict:
    return install_update(*args, **kwargs)


def launch_installer(*args: Any, **kwargs: Any) -> dict:
    return install_update(*args, **kwargs)
