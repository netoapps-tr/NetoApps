from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

from neto_runtime_core import APP_DIR, get_runtime


BACKUP_ROOT = APP_DIR / "backups"
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_FILES = [
    "config.json",
    "hafiza.json",
    "memory.json",
    "settings.json",
    "APP_VERSION.txt",
    "neto_version.py",
    "neto_runtime_core.py",
    "neto_runtime_services.py",
    "neto_settings_page.py",
]


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(project_dir, label="manual", extra_files=None):
    runtime = get_runtime()
    task_id = runtime.tasks.create("NetOps yedeği oluşturuluyor", cancellable=False)

    project = Path(project_dir).resolve()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(char for char in str(label) if char.isalnum() or char in "-_")[:32]
    archive_path = BACKUP_ROOT / f"neto_{stamp}_{safe_label or 'backup'}.zip"

    names = list(DEFAULT_FILES)
    if extra_files:
        names.extend(str(item) for item in extra_files)

    files = []
    for name in dict.fromkeys(names):
        path = project / name
        if path.is_file():
            files.append(path)

    runtime.tasks.update(task_id, status="running", progress=0.05)

    manifest = {
        "created_at": time.time(),
        "project": str(project),
        "label": str(label),
        "files": {},
    }

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        total = max(1, len(files))
        for index, path in enumerate(files, 1):
            relative = path.relative_to(project).as_posix()
            archive.write(path, relative)
            manifest["files"][relative] = {
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            runtime.tasks.update(
                task_id,
                progress=0.05 + (index / total) * 0.85,
                detail=relative,
            )
        archive.writestr(
            "NETO_BACKUP_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    runtime.tasks.update(
        task_id,
        status="completed",
        progress=1.0,
        detail=str(archive_path),
    )
    return archive_path


def list_backups():
    values = []
    for path in sorted(BACKUP_ROOT.glob("neto_*.zip"), reverse=True):
        try:
            values.append({
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
            })
        except Exception:
            pass
    return values


def verify_backup(archive_path):
    path = Path(archive_path)
    if not path.is_file():
        return {"ok": False, "error": "Yedek bulunamadı"}

    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad = archive.testzip()
            if bad:
                return {"ok": False, "error": f"Bozuk ZIP üyesi: {bad}"}
            try:
                manifest = json.loads(
                    archive.read("NETO_BACKUP_MANIFEST.json").decode("utf-8")
                )
            except Exception:
                manifest = {}
        return {"ok": True, "manifest": manifest}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def restore_backup(project_dir, archive_path, make_pre_restore_backup=True):
    runtime = get_runtime()
    task_id = runtime.tasks.create("NetOps yedeği geri yükleniyor", cancellable=False)

    project = Path(project_dir).resolve()
    archive_path = Path(archive_path).resolve()

    verification = verify_backup(archive_path)
    if not verification.get("ok"):
        runtime.tasks.update(
            task_id,
            status="failed",
            detail=verification.get("error", "Doğrulama başarısız"),
        )
        raise RuntimeError(verification.get("error", "Yedek doğrulanamadı"))

    if make_pre_restore_backup:
        create_backup(project, label="pre_restore")

    temp_dir = BACKUP_ROOT / f"restore_{int(time.time())}_{os.getpid()}"
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True)

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            safe_members = []
            for member in archive.infolist():
                name = member.filename
                if name == "NETO_BACKUP_MANIFEST.json":
                    continue
                target = (temp_dir / name).resolve()
                if temp_dir.resolve() not in target.parents:
                    raise RuntimeError(f"Güvensiz yedek yolu: {name}")
                safe_members.append(member)
            archive.extractall(temp_dir, members=safe_members)

        files = [path for path in temp_dir.rglob("*") if path.is_file()]
        total = max(1, len(files))

        for index, source in enumerate(files, 1):
            relative = source.relative_to(temp_dir)
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_target = target.with_suffix(target.suffix + ".restore_tmp")
            shutil.copy2(source, temp_target)
            os.replace(temp_target, target)
            runtime.tasks.update(
                task_id,
                status="running",
                progress=index / total,
                detail=str(relative),
            )

        runtime.tasks.update(
            task_id,
            status="completed",
            progress=1.0,
            detail=str(archive_path),
        )
        return True
    except Exception as exc:
        runtime.tasks.update(task_id, status="failed", detail=str(exc))
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
