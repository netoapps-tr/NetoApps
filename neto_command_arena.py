"""Live, read-only command activity board for NetOps."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import re
import threading
from typing import Any


KIND_LABELS = {
    "status": "Sistem",
    "media": "Medya",
    "recovery": "Recovery",
    "command": "Komut",
    "error": "Reddedildi",
}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def classify_command(command: str, result: dict[str, Any] | None = None) -> str:
    """Classify a command for display only; this function never executes it."""
    result = result if isinstance(result, dict) else {}
    if result.get("ok") is False or result.get("error"):
        return "error"
    value = _normalize(command)
    if any(term in value for term in ("recovery", "kurtarma")):
        return "recovery"
    if any(term in value for term in ("şarkı", "sarki", "müzik", "muzik", "now playing", "oynat", "duraklat", "ses")):
        return "media"
    if any(term in value for term in ("ram", "bellek", "cpu", "işlemci", "islemci", "disk", "durum", "status", "pil")):
        return "status"
    return "command"


class CommandArenaModel:
    def __init__(self, max_events: int = 80) -> None:
        self.max_events = max(1, int(max_events))
        self._events: deque[dict[str, Any]] = deque(maxlen=self.max_events)
        self._lock = threading.Lock()

    def record(self, command: str, source: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        result = result if isinstance(result, dict) else {}
        event = {
            "at": datetime.now().strftime("%H:%M:%S"),
            "command": str(command or "boş komut").strip() or "boş komut",
            "source": str(source or "Yerel").strip() or "Yerel",
            "kind": classify_command(command, result),
            "ok": result.get("ok") is not False and not result.get("error"),
            "message": str(result.get("display_text") or result.get("error") or "Komut alındı."),
        }
        with self._lock:
            self._events.append(event)
        return dict(event)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._events]

    def stats(self) -> dict[str, int]:
        events = self.snapshot()
        errors = sum(1 for item in events if item["kind"] == "error")
        return {"total": len(events), "success": len(events) - errors, "errors": errors}

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


ARENA = CommandArenaModel()


def record_command(command: str, source: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    return ARENA.record(command, source, result)


def open_command_arena(parent: Any, palette: dict[str, str] | None = None) -> Any:
    """Open the activity board without creating a second application loop."""
    import customtkinter as ctk

    colors = {
        "bg": "#0b0f16",
        "card": "#151c27",
        "sidebar": "#111823",
        "text_main": "#eef3fb",
        "text_dim": "#8e9bb0",
        "neon": "#347ff5",
        "entry_border": "#2c3a4f",
        "button_hover": "#285fbb",
    }
    if isinstance(palette, dict):
        colors.update({key: value for key, value in palette.items() if value})

    window = ctk.CTkToplevel(parent)
    window.title("NetOps Komut Arenası")
    window.geometry("760x560")
    window.minsize(620, 420)
    window.configure(fg_color=colors["bg"])
    try:
        window.transient(parent)
        window.attributes("-topmost", True)
        window.after(500, lambda: window.attributes("-topmost", False))
    except Exception:
        pass

    shell = ctk.CTkFrame(window, fg_color=colors["card"], corner_radius=18,
                         border_width=1, border_color=colors["entry_border"])
    shell.pack(fill="both", expand=True, padx=14, pady=14)
    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.pack(fill="x", padx=18, pady=(16, 5))
    ctk.CTkLabel(header, text="KOMUT ARENASI", text_color=colors["text_main"],
                 font=("Segoe UI Semibold", 18)).pack(side="left")
    stats_label = ctk.CTkLabel(header, text="", text_color=colors["text_dim"],
                               font=("Segoe UI", 10))
    stats_label.pack(side="right")

    ctk.CTkLabel(shell, text="Telefon ve NetOps komutları canlı akışta görünür. Bu panel yalnızca izler.",
                 text_color=colors["text_dim"], font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=18)
    feed = ctk.CTkScrollableFrame(shell, fg_color=colors["sidebar"], corner_radius=14)
    feed.pack(fill="both", expand=True, padx=18, pady=14)

    def refresh() -> None:
        if not window.winfo_exists():
            return
        for child in feed.winfo_children():
            child.destroy()
        stats = ARENA.stats()
        stats_label.configure(text=f"{stats['total']} olay  |  {stats['success']} başarılı  |  {stats['errors']} hata")
        events = ARENA.snapshot()
        if not events:
            ctk.CTkLabel(feed, text="Henüz komut yok. Telefonda netops status yazmayı deneyin.",
                         text_color=colors["text_dim"], font=("Segoe UI", 11)).pack(pady=28)
        for event in reversed(events):
            accent = "#ff6b7a" if event["kind"] == "error" else colors["neon"]
            row = ctk.CTkFrame(feed, fg_color=colors["card"], corner_radius=12,
                               border_width=1, border_color=colors["entry_border"])
            row.pack(fill="x", padx=4, pady=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(9, 0))
            ctk.CTkLabel(top, text=KIND_LABELS.get(event["kind"], "Komut"), text_color=accent,
                         font=("Segoe UI Semibold", 10)).pack(side="left")
            ctk.CTkLabel(top, text=f"{event['source']}  •  {event['at']}", text_color=colors["text_dim"],
                         font=("Segoe UI", 9)).pack(side="right")
            ctk.CTkLabel(row, text=event["command"], text_color=colors["text_main"],
                         font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", padx=12, pady=(4, 0))
            ctk.CTkLabel(row, text=event["message"], text_color=colors["text_dim"],
                         font=("Segoe UI", 9), anchor="w", wraplength=650, justify="left").pack(fill="x", padx=12, pady=(0, 9))
        window.after(700, refresh)

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", padx=18, pady=(0, 14))
    ctk.CTkButton(footer, text="Akışı Temizle", width=110, height=32, corner_radius=9,
                  fg_color=colors["sidebar"], hover_color=colors["button_hover"],
                  command=lambda: (ARENA.clear(), refresh())).pack(side="left")
    ctk.CTkButton(footer, text="Kapat", width=90, height=32, corner_radius=9,
                  fg_color=colors["neon"], hover_color=colors["button_hover"],
                  command=window.destroy).pack(side="right")
    refresh()
    return window


__all__ = ["ARENA", "CommandArenaModel", "classify_command", "open_command_arena", "record_command"]
