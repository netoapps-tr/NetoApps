from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

FIRST_INSTALL_SCHEMA = 1
FIRST_INSTALL_MARKER_NAME = "first_install_complete.json"
FIRST_INSTALL_ASSET_GIF = "neto_first_install.gif"
FIRST_INSTALL_ASSET_WAV = "neto_first_install.wav"


def _local_app_data() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def first_install_dir() -> Path:
    override = os.environ.get("NETO_FIRST_INSTALL_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _local_app_data() / "NetoAssistant" / "installation"


def first_install_marker_path() -> Path:
    return first_install_dir() / FIRST_INSTALL_MARKER_NAME


def first_install_completed() -> bool:
    if os.environ.get("NETO_FORCE_FIRST_INSTALL", "").strip() == "1":
        return False
    try:
        return first_install_marker_path().is_file()
    except Exception:
        return False


def _write_marker(state: str) -> None:
    """Write the persistent first-run marker atomically.

    The marker is intentionally version-independent. Once the application has
    been installed/launched successfully, updates must not replay the setup
    animation unless the user explicitly removes the marker.
    """
    try:
        folder = first_install_dir()
        folder.mkdir(parents=True, exist_ok=True)
        marker = folder / FIRST_INSTALL_MARKER_NAME
        tmp = folder / (FIRST_INSTALL_MARKER_NAME + ".tmp")
        payload: dict[str, Any] = {
            "schema": FIRST_INSTALL_SCHEMA,
            "state": str(state),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "python": sys.version.split()[0],
        }
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, marker)
    except Exception:
        # First-run UI must never prevent the real application from opening.
        # A plain marker is a final fallback when atomic replacement is blocked
        # by antivirus or an unusual filesystem policy.
        try:
            folder = first_install_dir()
            folder.mkdir(parents=True, exist_ok=True)
            (folder / FIRST_INSTALL_MARKER_NAME).touch(exist_ok=True)
        except Exception:
            pass


def _asset_path(payload_dir: Path, filename: str) -> Path:
    candidates = [
        payload_dir / filename,
        Path(__file__).resolve().parent / filename,
        Path.cwd() / filename,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return candidates[0]


def _play_sound_async(wav_path: Path) -> None:
    if os.name != "nt" or not wav_path.is_file():
        return
    try:
        import winsound

        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        winsound.PlaySound(str(wav_path), flags)
    except Exception:
        pass


def _stop_sound() -> None:
    if os.name != "nt":
        return
    try:
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


def _run_gif_window(gif_path: Path, wav_path: Path) -> None:
    import tkinter as tk

    try:
        from PIL import Image, ImageSequence, ImageTk
    except Exception:
        _run_fallback_window(wav_path)
        return

    root = tk.Tk()
    root.withdraw()
    root.configure(bg="#070709")
    root.overrideredirect(True)
    try:
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.0)
    except Exception:
        pass

    width = 392
    height = 392
    try:
        screen_w = max(width, int(root.winfo_screenwidth()))
        screen_h = max(height, int(root.winfo_screenheight()))
    except Exception:
        screen_w, screen_h = 1280, 720
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    shell = tk.Frame(root, bg="#070709", bd=0, highlightthickness=0)
    shell.pack(fill="both", expand=True)
    label = tk.Label(shell, bg="#070709", bd=0, highlightthickness=0)
    label.place(relx=0.5, rely=0.5, anchor="center")

    frames: list[ImageTk.PhotoImage] = []
    delays: list[int] = []
    with Image.open(gif_path) as image:
        for frame in ImageSequence.Iterator(image):
            converted = frame.convert("RGB").resize((360, 360), Image.Resampling.LANCZOS)
            frames.append(ImageTk.PhotoImage(converted, master=root))
            delay = int(frame.info.get("duration", image.info.get("duration", 45)) or 45)
            delays.append(max(25, min(250, delay)))

    if not frames:
        root.destroy()
        return

    closed = False

    def close_window() -> None:
        nonlocal closed
        if closed:
            return
        closed = True
        _stop_sound()
        try:
            root.attributes("-alpha", 0.0)
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    def show_frame(index: int = 0) -> None:
        if closed:
            return
        if index >= len(frames):
            # Keep the window alive long enough for the provided 2.30 s sound
            # to finish instead of cutting its final transient.
            root.after(180, close_window)
            return
        try:
            label.configure(image=frames[index])
            setattr(label, "image", frames[index])
        except Exception:
            close_window()
            return
        root.after(delays[index], lambda: show_frame(index + 1))

    # A hard ceiling prevents malformed GIF metadata from trapping startup.
    root.after(4200, close_window)
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    root.bind("<Alt-F4>", lambda _event: "break")

    root.deiconify()
    root.update_idletasks()
    try:
        root.attributes("-alpha", 1.0)
    except Exception:
        pass
    try:
        root.lift()
        root.focus_force()
    except Exception:
        pass

    _play_sound_async(wav_path)
    root.after(0, show_frame)
    root.mainloop()


def _run_fallback_window(wav_path: Path) -> None:
    """Dependency-free fallback shown only if Pillow cannot load the GIF."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.configure(bg="#070709")
    root.overrideredirect(True)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    width = 360
    height = 360
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    canvas = tk.Canvas(root, width=width, height=height, bg="#070709", bd=0, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_text(180, 170, text="NetOps", fill="white", font=("Segoe UI Semibold", 23))
    canvas.create_text(180, 205, text="İlk kurulum hazırlanıyor", fill="#b7b7bd", font=("Segoe UI", 11))
    root.deiconify()
    _play_sound_async(wav_path)

    def close_window() -> None:
        _stop_sound()
        try:
            root.destroy()
        except Exception:
            pass

    root.after(2400, close_window)
    root.mainloop()


def run_first_install(payload_dir: str | os.PathLike[str] | Path | None = None) -> bool:
    """Show the bundled installation animation exactly once per Windows user.

    This function is invoked only by the packaged EXE bootstrap, before the
    application's normal Start screen. Every exception is contained so a media,
    Tk or audio failure can never block NetOps from opening.
    """
    if os.environ.get("NETO_SKIP_FIRST_INSTALL", "").strip() == "1":
        return False
    if first_install_completed():
        return False

    payload = Path(payload_dir).resolve() if payload_dir is not None else Path(__file__).resolve().parent
    gif_path = _asset_path(payload, FIRST_INSTALL_ASSET_GIF)
    wav_path = _asset_path(payload, FIRST_INSTALL_ASSET_WAV)

    # Write an early marker before opening any GUI. If Windows, audio or Tk fails,
    # the user will not be trapped in a repeated broken setup loop on every launch.
    _write_marker("started")
    try:
        if gif_path.is_file():
            _run_gif_window(gif_path, wav_path)
        else:
            _run_fallback_window(wav_path)
    except BaseException:
        pass
    finally:
        _stop_sound()
        _write_marker("completed")
    return True


__all__ = [
    "FIRST_INSTALL_SCHEMA",
    "first_install_completed",
    "first_install_dir",
    "first_install_marker_path",
    "run_first_install",
]
