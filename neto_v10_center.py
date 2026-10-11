"""NetOps v10 Pulse window.

This is a deliberately small CustomTkinter view over ``neto_v10_features``.
It keeps diagnostics visible without adding another service or background loop.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import tkinter.messagebox as messagebox

import customtkinter as ctk

from neto_branding import apply_window_icon, get_ctk_image
from neto_v10_features import health_snapshot, rollback_driver


_WINDOW = None


def _toast(namespace: dict[str, Any], message: str, kind: str = "info") -> None:
    callback = namespace.get("neto_toast_goster") if isinstance(namespace, dict) else None
    if callable(callback):
        try:
            callback("NetOps v10", message, kind)
        except Exception:
            pass


def open_v10_pulse(root: Any, namespace: dict[str, Any] | None = None):
    global _WINDOW
    namespace = namespace or {}
    try:
        if _WINDOW is not None and _WINDOW.winfo_exists():
            _WINDOW.deiconify()
            _WINDOW.lift()
            _WINDOW.focus_force()
            return _WINDOW
    except Exception:
        _WINDOW = None

    project = Path(namespace.get("__file__", Path.cwd())).resolve().parent
    window = ctk.CTkToplevel(root)
    _WINDOW = window
    window.title("NetOps v10 Pulse")
    window.geometry("760x590")
    window.minsize(620, 480)
    window.configure(fg_color="#0B0B0F")
    apply_window_icon(window)
    try:
        window.transient(root)
    except Exception:
        pass

    shell = ctk.CTkFrame(window, fg_color="#15151B", border_width=1, border_color="#30303A", corner_radius=18)
    shell.pack(fill="both", expand=True, padx=14, pady=14)

    header = ctk.CTkFrame(shell, fg_color="transparent", height=70)
    header.pack(fill="x", padx=18, pady=(12, 0))
    header.pack_propagate(False)
    logo = get_ctk_image(42)
    ctk.CTkLabel(header, text="", image=logo, width=46, height=46).pack(side="left", padx=(0, 12), pady=8)
    title_box = ctk.CTkFrame(header, fg_color="transparent")
    title_box.pack(side="left", fill="both", expand=True)
    ctk.CTkLabel(title_box, text="NetOps v10 Pulse", text_color="#F4F4F5", anchor="w", font=("Segoe UI Semibold", 21)).pack(anchor="w")
    ctk.CTkLabel(title_box, text="Sürüm, sürücüler ve yerel sağlık tek ekranda", text_color="#A1A1AA", anchor="w", font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 0))

    content = ctk.CTkScrollableFrame(shell, fg_color="#101015", corner_radius=14, scrollbar_button_color="#373743")
    content.pack(fill="both", expand=True, padx=18, pady=(10, 12))

    def card(parent, title: str, value: str, detail: str = "", accent: str = "#22C55E"):
        frame = ctk.CTkFrame(parent, fg_color="#1B1B22", border_width=1, border_color="#30303A", corner_radius=12)
        frame.pack(fill="x", padx=3, pady=5)
        ctk.CTkLabel(frame, text="●", text_color=accent, font=("Segoe UI", 13)).pack(side="left", padx=(12, 8), pady=12)
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, pady=9)
        ctk.CTkLabel(body, text=title, text_color="#A1A1AA", anchor="w", font=("Segoe UI", 10)).pack(anchor="w")
        ctk.CTkLabel(body, text=value, text_color="#F4F4F5", anchor="w", font=("Segoe UI Semibold", 13)).pack(anchor="w", pady=(1, 0))
        if detail:
            ctk.CTkLabel(body, text=detail, text_color="#8B8B98", anchor="w", justify="left", wraplength=620, font=("Segoe UI", 10)).pack(anchor="w", pady=(1, 0))
        return frame

    def render():
        for child in content.winfo_children():
            child.destroy()
        try:
            snapshot = health_snapshot(project)
        except Exception as exc:
            card(content, "Pulse", "Sağlık verisi okunamadı", str(exc), "#F59E0B")
            return

        release = snapshot.get("release", {})
        doctor = snapshot.get("doctor", {})
        doctor_ok = bool(doctor.get("ok"))
        card(content, "Yayın", f"{release.get('name', 'NetOps One')} · {release.get('version', '10.37.0')}", f"Kanal: {release.get('channel', 'stable')} · {release.get('tag', 'v10.37.0')}", "#22C55E")
        card(content, "Mini Doktor", "Sistem hazır" if doctor_ok else "Kontrol gerekiyor", str(doctor.get("message") or "Yerel sağlık kontrolü tamamlandı."), "#22C55E" if doctor_ok else "#F59E0B")

        for driver in snapshot.get("drivers", []):
            component = str(driver.get("id") or "driver")
            label = "Görünüm sürücüsü" if component == "visual_driver" else "Now Playing sürücüsü"
            accent = "#22C55E" if driver.get("ok") else "#EF4444"
            card(content, label, f"v{driver.get('version', '0.0.0')}", f"Mod: {driver.get('mode', 'built-in')} · {component}", accent)

        highlights = release.get("highlights") or []
        if highlights:
            feature_text = "\n".join(f"• {item}" for item in highlights)
            card(content, "v10 bonus paketi", "NetOps One çekirdeği", feature_text, "#38BDF8")

        history = snapshot.get("histories", {})
        rollback_items = []
        for component, versions in history.items():
            if len(versions) > 1:
                rollback_items.append(f"{component}: {len(versions)} kayıt")
        if rollback_items:
            card(content, "Geri alma", "Önceki sürümler hazır", " · ".join(rollback_items), "#A78BFA")
        else:
            card(content, "Geri alma", "Henüz geçmiş sürüm yok", "Yeni doğrulanmış sürücüler kurulduğunda burada tutulur.", "#71717A")

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", padx=18, pady=(0, 14))

    def ask_rollback():
        choices = []
        try:
            current = health_snapshot(project).get("histories", {})
            for component, versions in current.items():
                if len(versions) > 1:
                    choices.append(component)
        except Exception:
            pass
        if not choices:
            _toast(namespace, "Geri alınabilecek önceki sürücü bulunamadı.", "info")
            return
        component = choices[0]
        try:
            result = rollback_driver(component)
            _toast(namespace, f"{component} v{result['version']} seçildi. Yeniden başlatınca etkin olacak.", "success")
            render()
        except Exception as exc:
            messagebox.showerror("NetOps v10", str(exc), parent=window)

    ctk.CTkButton(footer, text="Yenile", width=110, height=36, corner_radius=10, fg_color="#24242D", hover_color="#343440", command=render).pack(side="left")
    ctk.CTkButton(footer, text="Sürücüyü geri al", width=145, height=36, corner_radius=10, fg_color="#30234D", hover_color="#45306B", command=ask_rollback).pack(side="left", padx=8)
    ctk.CTkButton(footer, text="Kapat", width=100, height=36, corner_radius=10, fg_color="#22C55E", hover_color="#16A34A", command=window.destroy).pack(side="right")

    window.protocol("WM_DELETE_WINDOW", window.destroy)
    render()
    return window
