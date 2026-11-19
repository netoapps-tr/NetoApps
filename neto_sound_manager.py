"""Small, local sound override manager used by NetOps and Recovery Mode."""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path

from config import get_user_data_dir


SOUND_ROLES = ("recovery_warning", "startup", "update")
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg"}
_DEFAULT_ASSETS = {
    "recovery_warning": "assets/recovery-warning.mp3",
    "startup": "neto_startup_sound.mp3",
    "update": "neto_update_notification.mp3",
}


def _validate_role(role: str) -> str:
    value = str(role or "").strip().casefold()
    if value not in SOUND_ROLES:
        raise ValueError(f"Bilinmeyen ses rolü: {role}")
    return value


def _sound_dir(user_dir: str | Path | None = None) -> Path:
    base = Path(user_dir) if user_dir is not None else Path(get_user_data_dir())
    result = base / "sounds"
    result.mkdir(parents=True, exist_ok=True)
    return result


def _override_paths(role: str, user_dir: str | Path | None = None) -> list[Path]:
    role = _validate_role(role)
    return [_sound_dir(user_dir) / f"{role}{extension}" for extension in sorted(ALLOWED_EXTENSIONS)]


def resolve_override(role: str, user_dir: str | Path | None = None) -> Path | None:
    for path in _override_paths(role, user_dir):
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def resolve_sound(
    role: str,
    project_dir: str | Path = ".",
    *,
    user_dir: str | Path | None = None,
) -> Path | None:
    """Resolve a user override first, then the bundled project asset."""
    role = _validate_role(role)
    override = resolve_override(role, user_dir)
    if override is not None:
        return override
    bundled = Path(project_dir).resolve() / _DEFAULT_ASSETS[role]
    if bundled.is_file() and bundled.stat().st_size > 0:
        return bundled
    root_asset = Path(project_dir).resolve() / Path(_DEFAULT_ASSETS[role]).name
    if root_asset.is_file() and root_asset.stat().st_size > 0:
        return root_asset
    return None


def save_sound_override(
    role: str,
    source: str | Path,
    *,
    user_dir: str | Path | None = None,
) -> Path:
    role = _validate_role(role)
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError("Ses dosyası bulunamadı.")
    extension = source_path.suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Yalnızca MP3, WAV veya OGG sesleri kullanılabilir.")

    target_dir = _sound_dir(user_dir)
    target = target_dir / f"{role}{extension}"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{role}-", suffix=extension, dir=target_dir, delete=False
        ) as handle:
            temporary = Path(handle.name)
        shutil.copyfile(source_path, temporary)
        os.replace(temporary, target)
        for other in _override_paths(role, user_dir):
            if other != target and other.exists():
                other.unlink()
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target


def clear_sound_override(role: str, *, user_dir: str | Path | None = None) -> None:
    for path in _override_paths(role, user_dir):
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            if path.exists():
                path.unlink()


def play_sound_async(
    role: str,
    project_dir: str | Path = ".",
    *,
    volume: float = 0.65,
) -> bool:
    path = resolve_sound(role, project_dir)
    if path is None:
        return False

    def worker() -> None:
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            sound = pygame.mixer.Sound(str(path))
            sound.set_volume(max(0.0, min(1.0, float(volume))))
            sound.play()
        except Exception:
            return

    threading.Thread(target=worker, name=f"NetOpsSound-{role}", daemon=True).start()
    return True


__all__ = [
    "ALLOWED_EXTENSIONS",
    "SOUND_ROLES",
    "clear_sound_override",
    "play_sound_async",
    "resolve_override",
    "resolve_sound",
    "save_sound_override",
]
