"""Safe Windows update installer helpers for NetOps."""
from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
import uuid
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


def _can_write_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".netops-write-{os.getpid()}-{uuid.uuid4().hex}"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return True
    except (OSError, ValueError):
        return False


def _update_root() -> Path:
    """Find a writable updater directory without relying on Windows TEMP."""
    application_root = app_root().resolve()
    local_appdata = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    candidates = [
        Path(local_appdata) / "NetOps" / "updates" if local_appdata else None,
        Path(appdata) / "NetOps" / "updates" if appdata else None,
        Path.home() / ".neto_assistant" / "updates",
    ]
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir:
        candidates.append(Path(temp_dir) / "NetOps" / "updates")
    candidates.extend(
        [
            application_root.parent / ".neto_updates",
            Path.cwd() / ".neto_updates",
        ]
    )
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.resolve().relative_to(application_root)
            continue
        except ValueError:
            pass
        if _can_write_directory(candidate):
            return candidate
    raise RuntimeError("Güncelleme için yazılabilir klasör oluşturulamadı.")


def _new_job_workspace() -> Path:
    root = _update_root()
    for _ in range(5):
        candidate = root / f"job-{os.getpid()}-{uuid.uuid4().hex}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise RuntimeError(f"Güncelleme çalışma alanı oluşturulamadı: {exc}") from exc
    raise RuntimeError("Güncelleme çalışma alanı için benzersiz klasör oluşturulamadı.")


def _script_path(prefix: str) -> Path:
    root = _update_root()
    return root / f"{prefix}_{os.getpid()}_{uuid.uuid4().hex}.bat"


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
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
    job = _new_job_workspace()
    staging = job / "payload"
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            _safe_extract(archive, staging)
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise

    children = list(staging.iterdir())
    source = children[0] if len(children) == 1 and children[0].is_dir() else staging
    backup = job / "backup"
    script = _script_path("neto_apply_update")
    log_path = script.with_suffix(".log")
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
set "NETO_ROOT={str(root)}"
set "NETO_SOURCE={str(source)}"
set "NETO_BACKUP={str(backup)}"
echo [%date% %time%] Neto update started>"%NETO_LOG%"
ping 127.0.0.1 -n 5 >nul
robocopy "%NETO_ROOT%" "%NETO_BACKUP%" /E /R:3 /W:1 /NFL /NDL /NJH /NJS >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] Backup exit code: %RC%>>"%NETO_LOG%"
if %RC% GEQ 8 goto BACKUP_FAILED
robocopy "%NETO_SOURCE%" "%NETO_ROOT%" /E /IS /IT /R:5 /W:1 /NFL /NDL /NJH /NJS >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] Copy exit code: %RC%>>"%NETO_LOG%"
if %RC% GEQ 8 goto COPY_FAILED
{version_line}
{restart_line}
goto CLEANUP
:BACKUP_FAILED
echo [%date% %time%] Existing installation backup failed; no files changed.>>"%NETO_LOG%"
start "" notepad "%NETO_LOG%"
goto CLEANUP
:COPY_FAILED
echo [%date% %time%] Update copy failed; restoring previous installation.>>"%NETO_LOG%"
robocopy "%NETO_BACKUP%" "%NETO_ROOT%" /E /PURGE /R:3 /W:1 /NFL /NDL /NJH /NJS >>"%NETO_LOG%" 2>&1
echo [%date% %time%] Rollback exit code: %ERRORLEVEL%>>"%NETO_LOG%"
start "" notepad "%NETO_LOG%"
:CLEANUP
rmdir /s /q {_quote_bat(str(job))} >nul 2>&1
del "%~f0"
"""
    try:
        script.write_text(content, encoding="utf-8-sig")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise RuntimeError("Güncelleme kurulum betiği oluşturulamadı.")
    return script


def _exe_update_script(downloaded: Path, restart: bool, release_id: Any = None, tag: str = "") -> Path:
    """Replace a running one-file EXE after the application exits."""
    current_exe = Path(sys.executable).resolve()
    job = _new_job_workspace()
    backup = job / "NetOps.previous.exe"
    pending = job / "NetOps.pending.exe"
    script = _script_path("neto_apply_exe_update")
    log_path = script.with_suffix(".log")
    restart_cmd = current_command(
        [
            f"--neto-updated-release-id={release_id or ''}",
            f"--neto-updated-tag={tag or ''}",
        ]
    )
    restart_line = "start \"\" " + " ".join(_quote_bat(value) for value in restart_cmd) if restart else ""
    content = f"""@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "NETO_LOG={str(log_path)}"
set "NETO_EXE={str(current_exe)}"
set "NETO_DOWNLOAD={str(downloaded)}"
set "NETO_BACKUP={str(backup)}"
set "NETO_PENDING={str(pending)}"
echo [%date% %time%] Neto EXE update started>"%NETO_LOG%"
ping 127.0.0.1 -n 5 >nul
copy /Y "%NETO_EXE%" "%NETO_BACKUP%" >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] EXE backup exit code: %RC%>>"%NETO_LOG%"
if %RC% NEQ 0 goto BACKUP_FAILED
copy /Y "%NETO_DOWNLOAD%" "%NETO_PENDING%" >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
if %RC% NEQ 0 goto COPY_FAILED
move /Y "%NETO_PENDING%" "%NETO_EXE%" >>"%NETO_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] EXE replace exit code: %RC%>>"%NETO_LOG%"
if %RC% NEQ 0 goto COPY_FAILED
{restart_line}
goto CLEANUP
:BACKUP_FAILED
echo [%date% %time%] Existing EXE backup failed; original file was kept.>>"%NETO_LOG%"
start "" notepad "%NETO_LOG%"
goto CLEANUP
:COPY_FAILED
echo [%date% %time%] EXE replacement failed; restoring previous EXE.>>"%NETO_LOG%"
if exist "%NETO_BACKUP%" copy /Y "%NETO_BACKUP%" "%NETO_EXE%" >>"%NETO_LOG%" 2>&1
start "" notepad "%NETO_LOG%"
:CLEANUP
rmdir /s /q {_quote_bat(str(job))} >nul 2>&1
del "%~f0"
"""
    try:
        script.write_text(content, encoding="utf-8-sig")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise RuntimeError("EXE güncelleme betiği oluşturulamadı.")
    return script


def _safe_patch_path(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    path = Path(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise ValueError(f"Gecersiz sistem guncelleme yolu: {raw}")
    return raw.replace("/", "\\")


def install_file_update(
    plan: dict[str, Any],
    restart: bool = True,
    plan_path: str = "",
) -> dict:
    """Create a safe post-exit script for changing only listed system files."""
    if os.name != "nt":
        raise RuntimeError("Sistem dosyasi guncellemesi Windows icin tasarlandi.")
    if not isinstance(plan, dict) or plan.get("update_mode") != "system_files":
        raise ValueError("Sistem guncelleme plani gecersiz.")
    root = Path(str(plan.get("root") or app_root())).resolve()
    job = Path(str(plan.get("job") or "")).resolve()
    files = plan.get("files")
    if not job.is_dir() or not isinstance(files, list) or not files:
        raise RuntimeError("Sistem guncelleme staging alani bulunamadi.")

    records = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Sistem guncelleme planinda gecersiz dosya kaydi var.")
        relative = _safe_patch_path(item.get("path"))
        staged = Path(str(item.get("staged_path") or "")).resolve()
        try:
            staged.relative_to(job)
        except ValueError as exc:
            raise ValueError("Sistem guncelleme staging alani disina cikiyor.") from exc
        if not staged.is_file():
            raise FileNotFoundError(staged)
        target = (root / Path(relative)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Sistem guncelleme hedefi uygulama klasoru disinda.") from exc
        records.append((relative, staged, target))

    backup_root = job / "backup"
    history = _update_root() / "rollback" / f"{int(time.time())}-{uuid.uuid4().hex}"
    rollback_meta = {
        "root": str(root),
        "files": [relative for relative, _staged, _target in records],
        "backup": "backup",
        "created_at": int(time.time()),
    }
    (job / "rollback.json").write_text(
        json.dumps(rollback_meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    script = _script_path("neto_apply_system_update")
    log_path = script.with_suffix(".log")
    restart_cmd = current_command(
        [
            f"--neto-updated-tag={plan.get('release_tag') or plan.get('version') or ''}",
        ]
    )
    restart_line = "start \"\" " + " ".join(_quote_bat(value) for value in restart_cmd) if restart else ""
    backup_lines: list[str] = []
    copy_lines: list[str] = []
    rollback_lines: list[str] = []
    for index, (relative, staged, target) in enumerate(records):
        backup = backup_root / Path(relative)
        target_parent = target.parent
        backup_parent = backup.parent
        backup_lines.extend(
            [
                f"if exist {_quote_bat(str(target))} (",
                f"  if not exist {_quote_bat(str(backup_parent))} mkdir {_quote_bat(str(backup_parent))}",
                f"  copy /Y {_quote_bat(str(target))} {_quote_bat(str(backup))} >>\"%NETO_LOG%\" 2>&1",
                "  if errorlevel 1 goto BACKUP_FAILED",
                ")",
            ]
        )
        copy_lines.extend(
            [
                f"if not exist {_quote_bat(str(target_parent))} mkdir {_quote_bat(str(target_parent))}",
                f"copy /Y {_quote_bat(str(staged))} {_quote_bat(str(target))} >>\"%NETO_LOG%\" 2>&1",
                "if errorlevel 1 goto COPY_FAILED",
            ]
        )
        rollback_lines.extend(
            [
                f"if exist {_quote_bat(str(backup))} copy /Y {_quote_bat(str(backup))} {_quote_bat(str(target))} >>\"%NETO_LOG%\" 2>&1",
                f"if not exist {_quote_bat(str(backup))} del /Q {_quote_bat(str(target))} >nul 2>&1",
            ]
        )
    content = "\n".join(
        [
            "@echo off",
            "chcp 65001 >nul",
            "setlocal EnableExtensions",
            f"set \"NETO_LOG={log_path}\"",
            f"echo [%date% %time%] NetOps system file update started>\"%NETO_LOG%\"",
            "ping 127.0.0.1 -n 5 >nul",
            *backup_lines,
            *copy_lines,
            "echo [%date% %time%] Changed system files installed.>>\"%NETO_LOG%\"",
            f"rmdir /s /q {_quote_bat(str(job / 'payload'))} >nul 2>&1",
            f"if not exist {_quote_bat(str(history.parent))} mkdir {_quote_bat(str(history.parent))}",
            f"robocopy {_quote_bat(str(job))} {_quote_bat(str(history))} /E /R:3 /W:1 /NFL /NDL /NJH /NJS >>\"%NETO_LOG%\" 2>&1",
            "if %ERRORLEVEL% GEQ 8 goto COPY_FAILED",
            restart_line,
            "goto CLEANUP",
            ":BACKUP_FAILED",
            "echo [%date% %time%] Existing file backup failed; no update was applied.>>\"%NETO_LOG%\"",
            "start \"\" notepad \"%NETO_LOG%\"",
            "goto CLEANUP",
            ":COPY_FAILED",
            "echo [%date% %time%] File update failed; rolling back changed files.>>\"%NETO_LOG%\"",
            *rollback_lines,
            "start \"\" notepad \"%NETO_LOG%\"",
            ":CLEANUP",
            f"rmdir /s /q {_quote_bat(str(job))} >nul 2>&1",
            "del \"%~f0\"",
            "",
        ]
    )
    try:
        script.write_text(content, encoding="utf-8-sig")
    except Exception:
        raise RuntimeError("Sistem guncelleme kurulum betigi olusturulamadi.")
    subprocess.Popen(
        ["cmd", "/c", "start", "", str(script)],
        cwd=str(root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "ok": True,
        "mode": "system_files",
        "script": str(script),
        "file_count": len(records),
        "requires_exit": True,
    }


def install_rollback_update(record: dict[str, Any], restart: bool = True) -> dict:
    """Create a post-exit script that restores one persistent file backup."""
    if os.name != "nt":
        raise RuntimeError("Geri alma Windows icin tasarlandi.")
    if not isinstance(record, dict):
        raise ValueError("Geri alma kaydi gecersiz.")
    root = Path(str(record.get("root") or app_root())).resolve()
    history = Path(str(record.get("history_dir") or "")).resolve()
    backup_root = (history / str(record.get("backup") or "backup")).resolve()
    files = record.get("files")
    if not history.is_dir() or not backup_root.is_dir() or not isinstance(files, list) or not files:
        raise RuntimeError("Geri alinacak guvenli yedek bulunamadi.")

    job = _new_job_workspace()
    current_root = job / "current"
    records = []
    for raw in files:
        relative = _safe_patch_path(raw)
        target = (root / Path(relative)).resolve()
        old = (backup_root / Path(relative)).resolve()
        current = (current_root / Path(relative)).resolve()
        try:
            target.relative_to(root)
            old.relative_to(backup_root)
            current.relative_to(current_root)
        except ValueError as exc:
            shutil.rmtree(job, ignore_errors=True)
            raise ValueError("Geri alma yolu hedef klasor disinda.") from exc
        if old.exists() and not old.is_file():
            shutil.rmtree(job, ignore_errors=True)
            raise ValueError("Geri alma yedegi normal dosya degil.")
        records.append((target, old, current))

    script = _script_path("neto_rollback_system_update")
    log_path = script.with_suffix(".log")
    restart_cmd = current_command(["--neto-rollback-complete=1"])
    restart_line = "start \"\" " + " ".join(_quote_bat(value) for value in restart_cmd) if restart else ""
    backup_lines: list[str] = []
    restore_lines: list[str] = []
    rollback_lines: list[str] = []
    for target, old, current in records:
        backup_lines.extend(
            [
                f"if exist {_quote_bat(str(target))} (",
                f"  if not exist {_quote_bat(str(current.parent))} mkdir {_quote_bat(str(current.parent))}",
                f"  copy /Y {_quote_bat(str(target))} {_quote_bat(str(current))} >>\"%NETO_LOG%\" 2>&1",
                "  if errorlevel 1 goto BACKUP_FAILED",
                ")",
            ]
        )
        restore_lines.extend(
            [
                f"if exist {_quote_bat(str(old))} copy /Y {_quote_bat(str(old))} {_quote_bat(str(target))} >>\"%NETO_LOG%\" 2>&1",
                f"if not exist {_quote_bat(str(old))} del /Q {_quote_bat(str(target))} >nul 2>&1",
                "if errorlevel 1 goto RESTORE_FAILED",
            ]
        )
        rollback_lines.extend(
            [
                f"if exist {_quote_bat(str(current))} copy /Y {_quote_bat(str(current))} {_quote_bat(str(target))} >>\"%NETO_LOG%\" 2>&1",
                f"if not exist {_quote_bat(str(current))} del /Q {_quote_bat(str(target))} >nul 2>&1",
            ]
        )
    content = "\n".join(
        [
            "@echo off",
            "chcp 65001 >nul",
            "setlocal EnableExtensions",
            f"set \"NETO_LOG={log_path}\"",
            f"echo [%date% %time%] NetOps rollback started>\"%NETO_LOG%\"",
            "ping 127.0.0.1 -n 5 >nul",
            *backup_lines,
            *restore_lines,
            "echo [%date% %time%] Previous system files restored.>>\"%NETO_LOG%\"",
            restart_line,
            "goto CLEANUP",
            ":BACKUP_FAILED",
            "echo [%date% %time%] Current files could not be backed up; rollback cancelled.>>\"%NETO_LOG%\"",
            "start \"\" notepad \"%NETO_LOG%\"",
            "goto CLEANUP",
            ":RESTORE_FAILED",
            "echo [%date% %time%] Rollback failed; restoring current files.>>\"%NETO_LOG%\"",
            *rollback_lines,
            "start \"\" notepad \"%NETO_LOG%\"",
            ":CLEANUP",
            f"rmdir /s /q {_quote_bat(str(job))} >nul 2>&1",
            "del \"%~f0\"",
            "",
        ]
    )
    try:
        script.write_text(content, encoding="utf-8-sig")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise RuntimeError("Geri alma kurulum betigi olusturulamadi.")
    subprocess.Popen(
        ["cmd", "/c", "start", "", str(script)],
        cwd=str(root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {"ok": True, "mode": "system_rollback", "script": str(script), "requires_exit": True}


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
    if suffix == ".exe":
        if os.name == "nt" and getattr(sys, "frozen", False):
            script = _exe_update_script(target, restart=restart, release_id=release_id, tag=tag)
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(script)],
                cwd=str(app_root()),
                creationflags=creation_flags,
            )
            return {"ok": True, "mode": "exe_replace", "script": str(script), "requires_exit": True}
        subprocess.Popen([str(target)], cwd=str(target.parent), creationflags=creation_flags)
        return {"ok": True, "mode": "installer", "requires_exit": True}
    if suffix == ".msi":
        subprocess.Popen(["msiexec", "/i", str(target)], cwd=str(target.parent), creationflags=creation_flags)
        return {"ok": True, "mode": "installer", "requires_exit": True}
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(target)], creationflags=creation_flags)
    return {"ok": False, "mode": "unsupported", "path": str(target), "requires_exit": False}


def apply_update(*args: Any, **kwargs: Any) -> dict:
    return install_update(*args, **kwargs)


def launch_installer(*args: Any, **kwargs: Any) -> dict:
    return install_update(*args, **kwargs)
