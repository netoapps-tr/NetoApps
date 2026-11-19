"""Terminal-style Recovery Mode for NetOps.

The surface is deliberately a review console. It never executes arbitrary
shell text; phone requests are routed to ``recovery_command_answer`` and the
existing authenticated Device Hub.
"""
from __future__ import annotations

import re
import queue
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable


_ACTIVE_SURFACE: "RecoverySurface | None" = None


def is_recovery_command(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return normalized in {"/recovery netops", "recovery netops"}


def _normalized_recovery_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def is_recovery_confirmation(value: str) -> bool:
    return _normalized_recovery_text(value) in {
        "onayla",
        "onay",
        "evet",
        "confirm",
        "yes",
        "recovery onayla",
    }


def is_recovery_cancellation(value: str) -> bool:
    return _normalized_recovery_text(value) in {
        "iptal",
        "hayır",
        "hayir",
        "vazgeç",
        "vazgec",
        "cancel",
        "no",
    }


def is_recovery_exit(value: str) -> bool:
    return _normalized_recovery_text(value) in {
        "çıkış",
        "cıkıs",
        "cikis",
        "kapat",
        "exit",
    }


def recovery_confirmation_prompt() -> str:
    return (
        "Recovery Modu açılacak ve ana NetOps ekranı gizlenecek. "
        "Telefondan `onayla` yazın; vazgeçmek için `iptal` yazın."
    )


def transition_asset_path(project_dir: str | Path = ".") -> Path:
    root = Path(project_dir).resolve()
    bundled = root / "assets" / "Remote.gif"
    return bundled if bundled.is_file() else root / "Remote.gif"


def show_recovery_transition(
    root: Any,
    project_dir: str | Path,
    on_complete: Callable[[], None],
    *,
    duration_ms: int = 3000,
) -> Any:
    """Show the Remote logo briefly before opening Recovery Mode."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#000000")
    splash.attributes("-topmost", True)
    width, height = 420, 420
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    splash.geometry(f"{width}x{height}+{max(0, (screen_width - width) // 2)}+{max(0, (screen_height - height) // 2)}")

    frames: list[Any] = []
    asset = transition_asset_path(project_dir)
    try:
        from PIL import Image, ImageSequence, ImageTk

        image = Image.open(asset)
        for frame in ImageSequence.Iterator(image):
            frame = frame.convert("RGBA")
            frame.thumbnail((300, 300), Image.Resampling.LANCZOS)
            frames.append(ImageTk.PhotoImage(frame))
    except Exception:
        try:
            frames.append(tk.PhotoImage(file=str(asset)))
        except Exception:
            pass

    label = tk.Label(splash, bg="#000000", bd=0, highlightthickness=0)
    label.pack(fill="both", expand=True)
    index = 0

    def animate() -> None:
        nonlocal index
        if not splash.winfo_exists() or not frames:
            return
        label.configure(image=frames[index])
        index = (index + 1) % len(frames)
        splash.after(90, animate)

    def finish() -> None:
        try:
            if splash.winfo_exists():
                splash.destroy()
        finally:
            on_complete()

    splash.after(0, animate)
    splash.after(max(500, int(duration_ms)), finish)
    return splash


def build_boot_lines(seconds: int = 10) -> list[str]:
    total = max(1, min(30, int(seconds)))
    lines: list[str] = []
    for step in range(total):
        remaining = total - step
        code = f"RN-{step + 1:02d}-{remaining:02d}"
        lines.append(f"RECOVERY NETOPS [{remaining:02d}s] {code} :: güvenli çekirdek hazırlanıyor")
    return lines


def recovery_command_answer(text: str, project_dir: str | Path = ".") -> str:
    """Handle only read-only Recovery Mode chat commands."""
    value = re.sub(r"\s+", " ", str(text or "").strip().casefold())
    if any(term in value for term in ("yardım", "help", "komut")):
        return "Recovery izinli komutlar: durum, hata raporu, onarım planı, doğrula, çıkış."
    if any(term in value for term in ("durum", "hata", "kritik", "rapor", "log")):
        from neto_recovery_mesh import diagnose, format_plan

        return format_plan(diagnose(Path(project_dir).resolve()))
    if "onarım planı" in value or "onarim plani" in value or "plan" in value:
        from neto_recovery_mesh import diagnose

        plan = diagnose(Path(project_dir).resolve())
        steps = ", ".join(str(item.get("id")) for item in plan.get("steps") or []) or "işlem yok"
        return f"Recovery planı: {plan.get('status')}. Adımlar: {steps}. Açık onay olmadan uygulanmaz."
    if "doğrula" in value or "dogrula" in value or "test" in value:
        return "Doğrulama kuyruğa alındı; önce güvenli test planı ve mevcut hata sayısı karşılaştırılır."
    if is_recovery_exit(value):
        return "Recovery Mode kapanmaya hazır. Ana NetOps ekranı geri getiriliyor."
    return "Bu Recovery komutu izinli değil. `recovery yardım` yazarak güvenli komutları görebilirsiniz."


def record_event(message: str) -> None:
    surface = _ACTIVE_SURFACE
    if surface is not None:
        surface.append(f"[PHONE] {message}")


def request_recovery_close() -> bool:
    """Queue a safe close on Tk's event loop and restore the main window."""
    surface = _ACTIVE_SURFACE
    if surface is None:
        return False
    try:
        surface.window.after(0, surface.close)
        return True
    except Exception:
        return False


class RecoverySurface:
    def __init__(self, root: Any, project_dir: str | Path, on_close: Callable[[], None] | None = None) -> None:
        self.root = root
        self.project_dir = Path(project_dir).resolve()
        self.on_close = on_close
        self._events: queue.Queue[str] = queue.Queue()
        self.window = tk.Toplevel(root)
        self.window.title("Recovery NetOps")
        self.window.geometry("840x520")
        self.window.minsize(680, 420)
        self.window.configure(bg="#050609")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.transient(root)
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self.window.attributes("-topmost", True)
            self.window.after(500, lambda: self.window.attributes("-topmost", False))
        except Exception:
            pass

        self.output = tk.Text(
            self.window,
            bg="#050609",
            fg="#65f6a2",
            insertbackground="#65f6a2",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 11),
            padx=24,
            pady=22,
            wrap="word",
        )
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

        footer = tk.Frame(self.window, bg="#050609")
        footer.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(footer, text="Telefon komutları: durum · hata raporu · onarım planı · doğrula",
                 bg="#050609", fg="#78909c", font=("Segoe UI", 9)).pack(side="left")
        tk.Button(footer, text="Sesleri Yönet", command=self._open_sound_settings,
                  bg="#182335", fg="#eef3fb", activebackground="#263958",
                  activeforeground="#ffffff", relief="flat", padx=12, pady=7).pack(side="right", padx=(8, 0))
        tk.Button(footer, text="Ana NetOps'a dön", command=self.close,
                  bg="#182335", fg="#eef3fb", activebackground="#263958",
                  activeforeground="#ffffff", relief="flat", padx=14, pady=7).pack(side="right")

        global _ACTIVE_SURFACE
        _ACTIVE_SURFACE = self
        self.window.after(50, self._drain_events)
        self._boot()

    def append(self, message: str) -> None:
        self._events.put(str(message))

    def _drain_events(self) -> None:
        if not self.window.winfo_exists():
            return
        messages: list[str] = []
        while True:
            try:
                messages.append(self._events.get_nowait())
            except queue.Empty:
                break
        if messages:
            self.output.configure(state="normal")
            self.output.insert("end", "\n".join(item.rstrip() for item in messages) + "\n")
            self.output.see("end")
            self.output.configure(state="disabled")
        self.window.after(50, self._drain_events)

    def _boot(self) -> None:
        self.append("============================================================")
        self.append("                     RECOVERY NETOPS")
        self.append("         NetOps ana ekranı güvenli moda alınıyor...")
        self.append("============================================================")
        for index, line in enumerate(build_boot_lines(10), 1):
            self.window.after(index * 1000, lambda value=line: self.append(value))
        self.window.after(10500, self._online)

    def _online(self) -> None:
        self.append("")
        self.append("RECOVERY ONLINE :: Device Hub bağlantısı korunuyor")
        self.append("Telefon eşleşmesi üzerinden güvenli Recovery komutları bekleniyor.")
        self.append("Komutlar: recovery durum | recovery yardım | recovery onarım planı")

    def _open_sound_settings(self) -> None:
        try:
            from tkinter import filedialog
            from neto_sound_manager import (
                SOUND_ROLES,
                clear_sound_override,
                play_sound_async,
                resolve_override,
                save_sound_override,
            )

            panel = tk.Toplevel(self.window)
            panel.title("NetOps sesleri")
            panel.geometry("470x300")
            panel.configure(bg="#0b0f16")
            panel.transient(self.window)
            panel.grab_set()
            tk.Label(
                panel,
                text="NetOps sesleri",
                bg="#0b0f16",
                fg="#eef3fb",
                font=("Segoe UI Semibold", 15),
            ).pack(anchor="w", padx=18, pady=(18, 4))
            status = tk.StringVar(value="Yerel ses dosyası seçin.")
            tk.Label(
                panel,
                textvariable=status,
                bg="#0b0f16",
                fg="#9aa8bd",
                anchor="w",
                justify="left",
                wraplength=420,
            ).pack(fill="x", padx=18, pady=(0, 10))

            labels = {
                "recovery_warning": "Recovery uyarı sesi",
                "startup": "NetOps açılış sesi",
                "update": "Güncelleme bildirimi sesi",
            }
            for role in SOUND_ROLES:
                row = tk.Frame(panel, bg="#0b0f16")
                row.pack(fill="x", padx=18, pady=3)
                tk.Label(row, text=labels.get(role, role), width=24, anchor="w",
                         bg="#0b0f16", fg="#dce6f5").pack(side="left")

                def choose(current_role=role):
                    path = filedialog.askopenfilename(
                        parent=panel,
                        title="NetOps sesi seç",
                        filetypes=[("Ses dosyaları", "*.mp3 *.wav *.ogg"), ("Tüm dosyalar", "*.*")],
                    )
                    if not path:
                        return
                    try:
                        saved = save_sound_override(current_role, path)
                        status.set(f"Kaydedildi: {saved.name}")
                        self.append(f"Ses değiştirildi: {current_role} -> {saved.name}")
                    except Exception as exc:
                        status.set(f"Ses kaydedilemedi: {exc}")

                tk.Button(row, text="Değiştir", command=choose,
                          bg="#182335", fg="#eef3fb", relief="flat", padx=9).pack(side="right")
                if role == "recovery_warning":
                    tk.Button(row, text="Test", command=lambda r=role: play_sound_async(r, self.project_dir),
                              bg="#1c4d43", fg="#ffffff", relief="flat", padx=9).pack(side="right", padx=5)

                def clear(current_role=role):
                    clear_sound_override(current_role)
                    status.set(f"Varsayılan ses geri getirildi: {current_role}")

                tk.Button(row, text="Varsayılan", command=clear,
                          bg="#182335", fg="#eef3fb", relief="flat", padx=9).pack(side="right")

            tk.Button(panel, text="Kapat", command=panel.destroy,
                      bg="#263958", fg="#ffffff", relief="flat", padx=18, pady=7).pack(pady=16)
        except Exception as exc:
            self.append(f"Ses ayarları açılamadı: {exc}")

    def close(self) -> None:
        global _ACTIVE_SURFACE
        _ACTIVE_SURFACE = None
        try:
            self.window.destroy()
        finally:
            try:
                self.root.deiconify()
                self.root.lift()
            except Exception:
                pass
            if self.on_close:
                self.on_close()


def open_recovery_surface(root: Any, project_dir: str | Path, on_close: Callable[[], None] | None = None) -> RecoverySurface:
    return RecoverySurface(root, project_dir, on_close=on_close)


__all__ = [
    "RecoverySurface",
    "build_boot_lines",
    "is_recovery_cancellation",
    "is_recovery_confirmation",
    "is_recovery_command",
    "is_recovery_exit",
    "open_recovery_surface",
    "recovery_confirmation_prompt",
    "recovery_command_answer",
    "record_event",
    "request_recovery_close",
    "show_recovery_transition",
    "transition_asset_path",
]
