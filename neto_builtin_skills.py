"""Small, read-only skills shared by the desktop and remote command paths.

The catalog combines the useful shape of older assistant projects without
importing their application code. Skills only answer local read operations;
state-changing actions stay behind the existing permission and plugin APIs.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class BuiltinSkill:
    skill_id: str
    name: str
    description: str
    source_pattern: str
    triggers: tuple[str, ...]


_SKILLS = (
    BuiltinSkill("system", "Sistem", "CPU, RAM, disk ve pil durumunu okur.", "jarvis", ("cpu", "ram", "disk", "pil")),
    BuiltinSkill("media", "Medya", "Şu an çalan medya bilgisini okur.", "jarvis/zolppy", ("şimdi çalan", "ne çalıyor")),
    BuiltinSkill("devices", "Cihazlar", "NetOps bağlı cihazlarını listeler.", "hey-athena/mycroft", ("bağlı cihaz", "cihazları göster")),
    BuiltinSkill("help", "Komutlar", "Yerleşik skill komutlarını listeler.", "yoda/vassistant", ("komutlar", "yardım")),
    BuiltinSkill("recovery", "Recovery Mesh", "Hataları teşhis eder ve onay gerektiren geri dönüş planı çıkarır.", "netops", ("kendini onar", "kritik hata", "kurtarma", "hata taraması")),
)


def builtin_skills() -> tuple[BuiltinSkill, ...]:
    return _SKILLS


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _metrics() -> dict[str, Any]:
    try:
        import psutil

        vm = psutil.virtual_memory()
        total = float(getattr(vm, "total", 0) or 0)
        available = float(getattr(vm, "available", 0) or 0)
        used = max(0.0, total - available)
        battery = psutil.sensors_battery()
        disk_root = Path.home().anchor or os.getcwd()
        disk = shutil.disk_usage(disk_root)
        return {
            "cpu": round(float(psutil.cpu_percent(interval=None)), 0),
            "ram": round((used / total) * 100, 0) if total else 0,
            "ram_used_gb": round(used / (1024 ** 3), 1),
            "ram_total_gb": round(total / (1024 ** 3), 1),
            "disk_used_gb": round((disk.total - disk.free) / (1024 ** 3), 1),
            "disk_total_gb": round(disk.total / (1024 ** 3), 1),
            "battery": round(float(battery.percent), 0) if battery is not None else None,
        }
    except Exception:
        return {}


def _format_system(command: str, metrics: dict[str, Any]) -> str:
    cpu = _number(metrics.get("cpu"))
    ram = _number(metrics.get("ram"))
    ram_used = _number(metrics.get("ram_used_gb"))
    ram_total = _number(metrics.get("ram_total_gb"))
    disk_used = _number(metrics.get("disk_used_gb"))
    disk_total = _number(metrics.get("disk_total_gb"))
    battery = metrics.get("battery")
    parts: list[str] = []
    only_ram = bool(re.search(r"\b(?:ram|bellek)\b", command)) and not re.search(r"\b(?:cpu|işlemci|disk|depolama|pil|batarya)\b", command)
    only_cpu = bool(re.search(r"\b(?:cpu|işlemci)\b", command)) and not re.search(r"\b(?:ram|bellek|disk|depolama|pil|batarya)\b", command)
    only_disk = bool(re.search(r"\b(?:disk|depolama)\b", command)) and not re.search(r"\b(?:cpu|işlemci|ram|bellek|pil|batarya)\b", command)
    only_battery = bool(re.search(r"\b(?:pil|batarya)\b", command)) and not re.search(r"\b(?:cpu|işlemci|ram|bellek|disk|depolama)\b", command)

    if only_cpu:
        parts.append(f"CPU %{cpu:.0f}")
    elif only_ram:
        parts.extend(
            (
                f"CPU %{cpu:.0f}",
                f"RAM %{ram:.0f} ({ram_used:.1f}/{ram_total:.1f} GB)",
            )
        )
    elif only_disk:
        parts.append(f"Disk {disk_used:.1f}/{disk_total:.1f} GB")
    elif only_battery:
        parts.append(f"Pil %{battery:.0f}" if battery is not None else "Pil bilgisi kullanılamıyor")
    else:
        parts.extend(
            (
                f"CPU %{cpu:.0f}",
                f"RAM %{ram:.0f} ({ram_used:.1f}/{ram_total:.1f} GB)",
                f"Disk {disk_used:.1f}/{disk_total:.1f} GB",
                f"Pil %{battery:.0f}" if battery is not None else "Pil bilgisi kullanılamıyor",
            )
        )
    return " • ".join(parts) or "Sistem bilgisi alınamadı."


def _help_text() -> str:
    return (
        "Komutlar: sistem durumu, RAM durumu, CPU durumu, disk durumu, pil durumu, "
        "bağlı cihazlar, şimdi çalan, oynat/duraklat, sonraki, önceki, ses 0-100, "
        "Chrome aç, Edge aç, VS Code aç, Spotify aç, Not Defteri aç, "
        "Hesap Makinesi aç, Masaüstünü aç, Belgeleri aç, İndirilenler aç, "
        "PC kilitle, yardım ve normal sohbet."
    )


def handle(
    command: str,
    *,
    metrics_provider: Callable[[], dict[str, Any]] | None = None,
    media_provider: Callable[[], str] | None = None,
    device_provider: Callable[[], str] | None = None,
) -> str | None:
    """Return a read-only skill response or ``None`` for the normal engine."""
    value = _normalized(command)
    if not value:
        return None
    if value in {"yardım", "help", "komutlar", "komut listesi", "ne yapabilirsin"} or "komutlarını göster" in value:
        return _help_text()
    if (
        "recovery mesh" in value
        or "kendini onar" in value
        or "kritik hataları bul" in value
        or "kritik hatalari bul" in value
        or "onarım planı" in value
        or "onarim plani" in value
        or "sistem bozuldu" in value
    ):
        try:
            from neto_recovery_mesh import diagnose, format_plan

            return format_plan(diagnose(Path(__file__).resolve().parent))
        except Exception as exc:
            return f"Recovery Mesh çalışmadı; güvenli inceleme gerekli: {exc}"
    if any(term in value for term in ("şimdi çalan", "ne çalıyor", "şu an hangi şarkı", "şu an hangi müzik")):
        return media_provider() if media_provider is not None else "Şu an parça bilgisi yok."
    if any(term in value for term in ("bağlı cihaz", "cihazları göster", "cihaz listesi")):
        return device_provider() if device_provider is not None else "Kayıtlı bağlı cihaz yok."
    if (
        re.search(r"\b(?:cpu|işlemci|ram|bellek|disk|depolama|pil|batarya)\b", value)
        or "sistem durumu" in value
        or "sistem bilgisi" in value
    ):
        return _format_system(value, metrics_provider() if metrics_provider is not None else _metrics())
    return None


__all__ = ["BuiltinSkill", "builtin_skills", "handle"]
