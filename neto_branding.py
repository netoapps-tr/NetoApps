from __future__ import annotations

import ctypes
import os
import tkinter as tk
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    import customtkinter as ctk
except Exception:
    ctk = None


BASE_DIR = Path(__file__).resolve().parent
ICON_ICO = BASE_DIR / "neto_default_logo_v12.ico"
ICON_PNG = BASE_DIR / "neto_default_logo_v12.png"
APP_USER_MODEL_ID = "NetOps.Asistan.Desktop.V12"

_CTK_IMAGES: dict[int, Any] = {}
_TK_IMAGES: dict[int, Any] = {}
_INSTALLED_ROOTS: set[int] = set()


def set_windows_app_id() -> bool:
    if os.name != "nt":
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
        return True
    except Exception:
        return False


def asset_path(name: str = "neto_default_logo_v12.png") -> str:
    candidate = BASE_DIR / name
    if candidate.is_file():
        return str(candidate)
    return str(ICON_PNG)


def _load_source_image():
    if Image is None or not ICON_PNG.is_file():
        return None
    return Image.open(ICON_PNG).convert("RGBA")


def get_ctk_image(size: int = 32):
    size = max(12, int(size))
    if size in _CTK_IMAGES:
        return _CTK_IMAGES[size]
    if ctk is None:
        return None
    source = _load_source_image()
    if source is None:
        return None
    value = ctk.CTkImage(
        light_image=source,
        dark_image=source,
        size=(size, size),
    )
    _CTK_IMAGES[size] = value
    return value


def get_tk_image(size: int = 32):
    size = max(12, int(size))
    if size in _TK_IMAGES:
        return _TK_IMAGES[size]
    if Image is None or ImageTk is None:
        return None
    source = _load_source_image()
    if source is None:
        return None
    resampling = getattr(Image, "Resampling", None)
    filter_mode = getattr(resampling, "LANCZOS", None) if resampling is not None else None
    if filter_mode is None:
        filter_mode = getattr(Image, "LANCZOS", None)
    if filter_mode is None:
        return None
    value = ImageTk.PhotoImage(
        source.resize((size, size), filter_mode)
    )
    _TK_IMAGES[size] = value
    return value


def apply_window_icon(window) -> bool:
    if window is None:
        return False

    set_windows_app_id()
    changed = False

    try:
        if ICON_ICO.is_file():
            window.iconbitmap(default=str(ICON_ICO))
            changed = True
    except Exception:
        try:
            window.iconbitmap(str(ICON_ICO))
            changed = True
        except Exception:
            pass

    try:
        if ICON_PNG.is_file():
            icon = tk.PhotoImage(file=str(ICON_PNG))
            window.iconphoto(True, icon)
            setattr(window, "_neto_v12_window_icon", icon)
            changed = True
    except Exception:
        pass

    try:
        setattr(window, "_neto_v12_icon_applied", True)
    except Exception:
        pass
    return changed


def add_header_logo(
    frame,
    size: int = 32,
    position: str = "right",
    padx: int = 12,
    pady: int = 0,
):
    if frame is None:
        return None

    try:
        existing = getattr(frame, "_neto_v12_header_logo", None)
        if existing is not None and existing.winfo_exists():
            try:
                existing.lift()
            except Exception:
                pass
            return existing
    except Exception:
        pass

    def create():
        try:
            if not frame.winfo_exists():
                return None
        except Exception:
            return None

        try:
            ctk_module: Any = ctk
            is_ctk = ctk_module is not None and frame.__class__.__module__.startswith("customtkinter")
            if is_ctk:
                picture = get_ctk_image(size)
                if picture is None:
                    return None
                label = getattr(ctk_module, "CTkLabel")(
                    frame,
                    text="",
                    image=picture,
                    width=size + 2,
                    height=size + 2,
                    fg_color="transparent",
                    corner_radius=0,
                )
            else:
                picture = get_tk_image(size)
                if picture is None:
                    return None
                try:
                    background = frame.cget("bg")
                except Exception:
                    background = "#0B0B0F"
                label = tk.Label(
                    frame,
                    text="",
                    image=picture,
                    width=size,
                    height=size,
                    bg=background,
                    bd=0,
                    highlightthickness=0,
                )
            setattr(label, "_neto_v12_picture", picture)
            setattr(label, "_neto_branding_marker", True)

            if position == "left":
                label.place(x=padx, rely=0.5, anchor="w")
            elif position == "center":
                label.place(relx=0.5, rely=0.5, anchor="center")
            else:
                label.place(
                    relx=1.0,
                    x=-padx,
                    rely=0.5,
                    y=pady,
                    anchor="e",
                )
            label.lift()
            setattr(frame, "_neto_v12_header_logo", label)
            return label
        except Exception:
            return None

    try:
        return frame.after_idle(create)
    except Exception:
        return create()


def _walk(widget):
    yield widget
    try:
        for child in widget.winfo_children():
            yield from _walk(child)
    except Exception:
        return


def _is_toplevel(widget) -> bool:
    try:
        return widget.winfo_toplevel() is widget
    except Exception:
        return False


def _header_candidate(widget) -> bool:
    try:
        class_name = widget.__class__.__name__.casefold()
        if "frame" not in class_name:
            return False
        if getattr(widget, "_neto_v12_header_logo", None) is not None:
            return False
        width = int(widget.winfo_width())
        height = int(widget.winfo_height())
        if width < 260 or height < 42 or height > 125:
            return False
        top = widget.winfo_toplevel()
        relative_y = int(widget.winfo_rooty() - top.winfo_rooty())
        if relative_y > 150:
            return False

        text = []
        for child in widget.winfo_children():
            try:
                value = str(child.cget("text") or "").strip().casefold()
                if value:
                    text.append(value)
            except Exception:
                pass
        combined = " ".join(text)
        keywords = (
            "neto", "ayarlar", "settings", "code", "güncelle",
            "update", "android", "live", "komut", "command",
            "izin", "permission", "yedek", "backup",
        )
        return any(word in combined for word in keywords)
    except Exception:
        return False


def refresh_branding(root) -> None:
    try:
        if root is None or not root.winfo_exists():
            return
    except Exception:
        return

    tops = set()
    for widget in _walk(root):
        try:
            tops.add(widget.winfo_toplevel())
        except Exception:
            pass
        if _header_candidate(widget):
            add_header_logo(widget, size=29, position="right", padx=11)

    for top in tops:
        try:
            if not getattr(top, "_neto_v12_icon_applied", False):
                apply_window_icon(top)
        except Exception:
            pass


def install_branding(root, scan_interval_ms: int = 650) -> bool:
    if root is None:
        return False

    root_id = id(root)
    apply_window_icon(root)

    if root_id in _INSTALLED_ROOTS:
        refresh_branding(root)
        return True

    _INSTALLED_ROOTS.add(root_id)

    def scan():
        try:
            if not root.winfo_exists():
                return
        except Exception:
            return
        refresh_branding(root)
        try:
            root.after(max(400, int(scan_interval_ms)), scan)
        except Exception:
            pass

    try:
        root.after(80, scan)
    except Exception:
        scan()
    return True


install_neto_branding = install_branding
brand_window = apply_window_icon
decorate_header = add_header_logo
