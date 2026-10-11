from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

APP_NAME = "NetOps"
BG = "#09090B"
CARD = "#17171C"
BORDER = "#34343D"
TEXT = "#F4F4F5"
MUTED = "#A1A1AA"
ACCENT = "#22C55E"
ACCENT_DARK = "#15803D"
RED = "#EF4444"


def _single_instance() -> object | None:
    if os.name != "nt":
        return object()
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\NetoAssistantQuickLauncherV5")
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            return None
        return handle
    except Exception:
        return object()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _session_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    folder = base / "NetoAssistant" / "quick_sessions"
    folder.mkdir(parents=True, exist_ok=True)
    # Eski oturumları temizle.
    cutoff = time.time() - (3 * 24 * 3600)
    for child in folder.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                import shutil
                shutil.rmtree(child, ignore_errors=True)
        except Exception:
            pass
    session = folder / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{os.getpid()}"
    session.mkdir(parents=True, exist_ok=True)
    return session


class QuickLauncher:
    def __init__(self, root: tk.Tk, safe_mode: bool = True):
        self.root = root
        self.safe_mode = bool(safe_mode)
        self.launch_mode = "force" if self.safe_mode else "normal"
        self.deadline_seconds = 5.0 if self.safe_mode else 30.0
        self.deadline_handled = False
        self.base = Path(__file__).resolve().parent
        self.app_file = self.base / "asistan beta.py"
        self.session = _session_root()
        self.log_path = self.session / "child.log"
        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.start_time = time.perf_counter()
        self.start_requested = False
        self.ready = False
        self.shown = False
        self.closed = False
        self.last_output = ""
        self.language = tk.StringVar(value="tr")
        self.status = tk.StringVar(value="Ana uygulama hazırlanıyor…")
        self.timer = tk.StringVar(value="0.0 sn")
        self.progress_value = 0.04

        self._configure_window()
        self._build_ui()
        self._start_child()
        # V7: Başlat düğmesini beklemeden otomatik başlat.
        self.root.after(120, self.request_start)
        self.root.after(80, self._poll)
        self.root.after(40, self._animate)

    def _configure_window(self):
        self.root.title(APP_NAME)
        self.root.geometry("560x340")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            ico = self.base / "neto_titlebar_logo.ico"
            if ico.is_file():
                self.root.iconbitmap(str(ico))
        except Exception:
            pass
        try:
            png = self.base / "neto_titlebar_logo.png"
            if png.is_file():
                self._neto_window_icon = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._neto_window_icon)
        except Exception:
            self._neto_window_icon = None
        try:
            self.root.attributes("-topmost", True)
            self.root.after(700, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        self.root.update_idletasks()
        width, height = 560, 340
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG, highlightbackground=BORDER, highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", padx=34, pady=(22, 0))
        try:
            logo_path = self.base / "neto_titlebar_logo.png"
            self._neto_logo_photo = tk.PhotoImage(file=str(logo_path))
            tk.Label(
                header, image=self._neto_logo_photo, bg=BG,
                bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 14))
        except Exception:
            self._neto_logo_photo = None

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left")
        tk.Label(
            title_box, text="NETOPS", bg=BG, fg=TEXT,
            font=("Segoe UI Semibold", 25),
        ).pack(anchor="w")
        mode_text = (
            "Zorla hızlı mod · başlatıcı üst sınırı 5 sn"
            if self.safe_mode else
            "Normal mod · başlatıcı üst sınırı 30 sn"
        )
        tk.Label(
            title_box, text=mode_text, bg=BG, fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))

        middle = tk.Frame(outer, bg=BG)
        middle.pack(fill="x", padx=34, pady=(18, 0))

        tk.Label(middle, textvariable=self.status, bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 12), anchor="w").pack(side="left")
        tk.Label(middle, textvariable=self.timer, bg=BG, fg=MUTED,
                 font=("Consolas", 10), anchor="e").pack(side="right")

        self.canvas = tk.Canvas(outer, width=492, height=8, bg=CARD, bd=0, highlightthickness=0)
        self.canvas.pack(padx=34, pady=(13, 22))
        self.progress_rect = self.canvas.create_rectangle(0, 0, 18, 8, fill=ACCENT, outline="")

        controls = tk.Frame(outer, bg=BG)
        controls.pack(fill="x", padx=34)

        lang_frame = tk.Frame(controls, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        lang_frame.pack(side="left")
        for text, value in (("Türkçe", "tr"), ("English", "en")):
            tk.Radiobutton(
                lang_frame, text=text, value=value, variable=self.language,
                bg=CARD, activebackground=CARD, fg=TEXT, activeforeground=TEXT,
                selectcolor=BG, font=("Segoe UI", 10), bd=0, padx=9, pady=7,
            ).pack(side="left")

        self.start_button = tk.Button(
            controls, text="Başlat", command=self.request_start,
            bg=ACCENT, activebackground=ACCENT_DARK, fg="#07110A",
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Segoe UI Semibold", 12), padx=34, pady=10, cursor="hand2",
        )
        self.start_button.pack(side="right")

        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", padx=34, pady=(26, 0))
        mode_text = "Kararlı mod: açık" if self.safe_mode else "Normal mod"
        self.mode_label = tk.Label(footer, text=mode_text, bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.mode_label.pack(side="left")
        tk.Button(
            footer, text="Teşhis", command=self.open_doctor,
            bg=BG, activebackground=CARD, fg=MUTED, activeforeground=TEXT,
            relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2",
        ).pack(side="right")

    def _child_command(self) -> list[str]:
        return [sys.executable, str(self.app_file)]

    def _start_child(self):
        if not self.app_file.is_file():
            self.status.set("asistan beta.py bulunamadı")
            self.start_button.configure(state="disabled", bg=RED)
            return
        env = os.environ.copy()
        env["NETO_QUICK_LAUNCH_CHILD"] = "1"
        env["NETO_QUICK_SESSION_DIR"] = str(self.session)
        env["NETO_STABLE_MODE"] = "1" if self.safe_mode else "0"
        env["NETO_LAUNCH_MODE"] = self.launch_mode
        env["NETO_FORCE_SHOW_SECONDS"] = str(int(self.deadline_seconds))
        env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        env["PYTHONUTF8"] = "1"
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                self._child_command(), cwd=self.base, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=flags,
            )
        except Exception as exc:
            self.status.set(f"Ana uygulama başlatılamadı: {exc}")
            self.start_button.configure(state="disabled", bg=RED)
            return
        threading.Thread(target=self._capture_output, daemon=True).start()

    def _capture_output(self):
        process = self.process
        if process is None or process.stdout is None:
            return
        try:
            with self.log_path.open("a", encoding="utf-8") as log:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    self.output_queue.put(line.rstrip())
        except Exception:
            try:
                self.log_path.write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:
                pass

    def request_start(self):
        if self.process is None:
            return
        self.start_requested = True
        _write_json(
            self.session / "go.json",
            {
                "language": self.language.get(),
                "requested": time.time(),
                "safe_mode": self.safe_mode,
                "mode": self.launch_mode,
                "deadline_seconds": self.deadline_seconds,
                "auto_start": True,
            },
        )
        if self.ready:
            self.status.set("Neto açılıyor…")
        else:
            self.status.set("Başlatma istendi · hazırlık tamamlanıyor…")
        self.start_button.configure(state="disabled", text="Bekleniyor…")

    def _animate(self):
        if self.closed:
            return
        elapsed = time.perf_counter() - self.start_time
        self.timer.set(f"{elapsed:.1f} sn")
        if self.ready:
            target = 0.96
        else:
            target = min(0.88, 0.08 + elapsed / 15.0)
        self.progress_value += (target - self.progress_value) * 0.16
        width = int(492 * max(0.02, min(1.0, self.progress_value)))
        self.canvas.coords(self.progress_rect, 0, 0, width, 8)
        self.root.after(40, self._animate)

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                self.last_output = self.output_queue.get_nowait()
        except queue.Empty:
            pass

        window_file = self.session / "window.json"
        ready_file = self.session / "ready.json"
        shown_file = self.session / "shown.json"

        # V7: Gerçek NetOps penceresi görünür görünmez başlatıcı kapanır.
        if window_file.is_file():
            self.shown = True
            self.progress_value = 1.0
            info = _read_json(window_file)
            seconds = info.get("window_seconds")
            suffix = f" · {seconds} sn" if seconds is not None else ""
            self.status.set(f"NetOps penceresi açıldı{suffix}")
            self.root.after(120, self._finish)
            return
        if not self.ready and ready_file.is_file():
            self.ready = True
            info = _read_json(ready_file)
            seconds = info.get("ready_seconds")
            self.status.set(f"Hazır{f' · {seconds} sn' if seconds is not None else ''}")
            if not self.start_requested:
                self.start_button.configure(state="normal", text="Başlat", bg=ACCENT)
            else:
                self.status.set("Neto açılıyor…")

        if shown_file.is_file():
            self.shown = True
            self.progress_value = 1.0
            self.status.set("Açıldı")
            self.root.after(100, self._finish)
            return

        elapsed = time.perf_counter() - self.start_time
        if (
            elapsed >= self.deadline_seconds
            and not self.deadline_handled
            and not self.shown
        ):
            self.deadline_handled = True
            try:
                _write_json(
                    self.session / "force_show.json",
                    {
                        "requested": time.time(),
                        "mode": self.launch_mode,
                        "deadline_seconds": self.deadline_seconds,
                    },
                )
            except Exception:
                pass
            self.status.set(
                f"{int(self.deadline_seconds)} sn sınırı doldu · başlatıcı kapanıyor"
            )
            # Ana uygulama çalışmaya devam eder; başlatıcı arkada kalmaz.
            self.root.after(500, self._finish)
            return

        process = self.process
        if process is not None and process.poll() is not None and not self.shown:
            code = process.returncode
            tail = self.last_output or "Ayrıntı child.log dosyasında."
            self.status.set(f"Ana uygulama kapandı · kod {code}")
            self.start_button.configure(
                state="normal", text="Güvenli yeniden dene", bg=RED,
                command=self.retry_safe,
            )
            self.mode_label.configure(text=tail[:90], fg=RED)
            return

        self.root.after(100, self._poll)

    def retry_safe(self):
        self.safe_mode = True
        self.start_requested = False
        self.ready = False
        self.shown = False
        self.last_output = ""
        self.start_time = time.perf_counter()
        self.session = _session_root()
        self.log_path = self.session / "child.log"
        self.mode_label.configure(text="Kararlı mod: açık", fg=MUTED)
        self.deadline_handled = False
        self.start_button.configure(state="normal", text="Başlat", bg=ACCENT, command=self.request_start)
        self.status.set("Yeniden hazırlanıyor…")
        self._start_child()
        self.root.after(100, self._poll)

    def open_doctor(self):
        doctor = self.base / "neto_doctor.py"
        if not doctor.is_file():
            messagebox.showerror(APP_NAME, "neto_doctor.py bulunamadı.", parent=self.root)
            return
        try:
            subprocess.Popen([sys.executable, str(doctor), "--project", str(self.base)], cwd=self.base)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)

    def _finish(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            _write_json(self.session / "cancel.json", {"cancelled": time.time()})
        except Exception:
            pass
        process = self.process
        if process is not None and process.poll() is None and not self.shown:
            try:
                process.terminate()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass


def main() -> int:
    mutex = _single_instance()
    if mutex is None:
        try:
            root = tk.Tk(); root.withdraw()
            messagebox.showinfo(APP_NAME, "NetOps başlatıcısı zaten açık.")
            root.destroy()
        except Exception:
            pass
        return 0
    safe_mode = "--normal" not in sys.argv
    root = tk.Tk()
    QuickLauncher(root, safe_mode=safe_mode)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
