# NetOps startup UI
# v14.3: single-mainloop, non-blocking welcome/loading gate.

import json
import math
import os
import re
import time
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageSequence

LOGO_CANDIDATES = [
    "NetoAsistan.png", "Logo.png", "yukleme.gif", "Neto.gif", "kevra.png", "kevr.png",
    "NetoAsistan.ico", "Logo.ico", "kevra.ico", "kevr.ico",
]
INTRO_GIF_CANDIDATES = [
    # v1.40: kullanıcının seçtiği logo animasyonu en başta denenir.
    "neto_intro_logo.gif",
    "neto_logo_7click.gif",
    "neto_main_logo_source.gif",
    "Neto.gif",
    "neto_first_install.gif",
]

GATE_COLORS = {
    "bg": "#050816",
    "shell": "#0A1024",
    "card": "#0E1730",
    "card_soft": "#111C39",
    "border": "#2E5BFF",
    "border_soft": "#213A75",
    "text": "#F7FAFF",
    "text_dim": "#B9C4E0",
    "accent": "#68A7FF",
    "accent_hover": "#7FC0FF",
    "progress": "#5A9CFF",
}


def _clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, float(value)))


def _ease_fluid(t):
    t = _clamp(t)
    if t >= 1.0:
        return 1.0
    expo = 1.0 - (2.0 ** (-8.0 * t))
    smooth = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    return _clamp((expo * 0.72) + (smooth * 0.28))


def _mix_hex_color(start, end, progress):
    try:
        s = str(start).lstrip("#")
        e = str(end).lstrip("#")
        sr, sg, sb = [int(s[i : i + 2], 16) for i in (0, 2, 4)]
        er, eg, eb = [int(e[i : i + 2], 16) for i in (0, 2, 4)]
        p = _clamp(progress)
        return "#%02X%02X%02X" % (
            round(sr + (er - sr) * p),
            round(sg + (eg - sg) * p),
            round(sb + (eb - sb) * p),
        )
    except Exception:
        return str(end)


def center_window(win, width, height):
    try:
        win.update_idletasks()
        x = max(0, int((win.winfo_screenwidth() - width) / 2))
        y = max(0, int((win.winfo_screenheight() - height) / 2) - 18)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        win.geometry(f"{width}x{height}")


def _resolve_asset(get_asset_path, name):
    try:
        path = get_asset_path(name)
    except Exception:
        path = name
    return path if path and os.path.exists(path) else ""


def set_window_icon(win, get_asset_path):
    try:
        icon_path = _resolve_asset(get_asset_path, "NetoAsistan.ico") or _resolve_asset(get_asset_path, "Logo.ico")
        if icon_path:
            win.iconbitmap(icon_path)
    except Exception:
        pass


def load_logo_image(get_asset_path, max_size=(96, 96)):
    for name in LOGO_CANDIDATES:
        path = _resolve_asset(get_asset_path, name)
        if not path:
            continue
        try:
            image = Image.open(path)
            try:
                image.seek(0)
            except Exception:
                pass
            image = image.convert("RGBA")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        except Exception:
            continue
    return None


def load_intro_animation(get_asset_path, max_size=(360, 360)):
    """Load the animated logo splash used before the Start screen."""
    for name in INTRO_GIF_CANDIDATES:
        path = _resolve_asset(get_asset_path, name)
        if not path:
            continue
        try:
            image = Image.open(path)
            frames = []
            delays = []
            for frame in ImageSequence.Iterator(image):
                converted = frame.convert("RGBA")
                converted.thumbnail(max_size, Image.Resampling.LANCZOS)
                frames.append(converted.copy())
                raw_delay = int(frame.info.get("duration", image.info.get("duration", 40)) or 40)
                delays.append(max(18, min(72, int(raw_delay * 0.8))))
            if frames:
                return frames, delays, path
        except Exception:
            continue
    return None, None, None


def _texts(lang):
    if str(lang or "en").lower().startswith("tr"):
        return {
            "window": "NetOps'e Hoş Geldin",
            "title": "NetOps'e Hoş Geldin",
            "description": "Uygulamayı başlatmadan önce dilini ve Live Mode ayarını seç.",
            "intro_title": "NetOps",
            "intro_status": "Başlat menüsü hazırlanıyor",
            "live": "Açılıştan sonra Live Mode'u otomatik başlat",
            "hint": "Ana arayüz tamamen hazırlandı; Başlat'a bastığında doğrudan açılır.",
            "start": "Başlat",
            "starting": "NetOps açılıyor...",
            "ready": "Ana arayüz hazır",
            "apply": "Seçimler uygulanıyor",
            "show": "Pencere açılıyor",
        }
    return {
        "window": "Welcome to NetOps",
        "title": "Welcome to NetOps",
        "description": "Choose the language and Live Mode option before starting.",
        "intro_title": "NetOps",
        "intro_status": "Preparing the Start menu",
        "live": "Start Live Mode automatically after launch",
        "hint": "The main interface is already prepared and opens immediately after Start.",
        "start": "Start",
        "starting": "Opening NetOps...",
        "ready": "Main interface is ready",
        "apply": "Applying selections",
        "show": "Showing window",
    }


def _quick_session_root() -> Path | None:
    raw = os.environ.get("NETO_QUICK_SESSION_DIR", "").strip()
    if not raw:
        return None
    try:
        root = Path(raw).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root
    except Exception:
        return None


def _quick_write_state(filename: str, payload: dict) -> None:
    root = _quick_session_root()
    if root is None:
        return
    path = root / filename
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except Exception:
        try:
            if temp.exists():
                temp.unlink()
        except Exception:
            pass


def _play_intro_sound(path):
    """Giriş sesini çalar (pygame). Başarısız olursa sessizce devam eder."""
    try:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        sound = pygame.mixer.Sound(str(path))
        sound.play()
        return sound
    except Exception:
        return None


def run_logo_intro(root, data, on_started=None, get_asset_path=None, max_seconds=9.0):
    """Logo animasyonu + ses ile otomatik açılış (v1.40 eklentisi).

    Klasik "Başlat" kapısının YERİNE geçer: animasyon ve ses biter bitmez
    ana arayüz kendiliğinden açılır; düğme yoktur. Tıklama veya tuş ile
    atlanabilir.

    Varlık dosyaları bulunamazsa ``None`` döner; çağıran taraf klasik
    kapıya geri döner (bu yüzden davranış asla bozulmaz).
    """
    frames, delays, asset_path = load_intro_animation(get_asset_path, (360, 360))
    if not frames:
        return None

    sound_path = _resolve_asset(get_asset_path, "neto_intro_logo.mp3")

    try:
        root.withdraw()
        root.attributes("-alpha", 1.0)
    except Exception:
        pass

    win = ctk.CTkToplevel(root)
    win.title("NetOps")
    win.geometry("420x420")
    win.resizable(False, False)
    win.configure(fg_color="#000000")
    try:
        win.overrideredirect(True)
    except Exception:
        pass
    try:
        center_window(win, 420, 420)
    except Exception:
        pass
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    try:
        win.protocol("WM_DELETE_WINDOW", lambda: None)
    except Exception:
        pass
    set_window_icon(win, get_asset_path)

    holder = ctk.CTkLabel(win, text="", fg_color="#000000")
    holder.pack(fill="both", expand=True)

    images = []
    for frame in frames:
        try:
            images.append(ctk.CTkImage(light_image=frame, dark_image=frame, size=frame.size))
        except Exception:
            images.append(None)

    if sound_path:
        _play_intro_sound(sound_path)

    state = {"done": False, "job": None}

    def finish(*_args):
        if state["done"]:
            return
        state["done"] = True
        try:
            if state["job"] is not None:
                win.after_cancel(state["job"])
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        # Klasik finish_reveal() ile aynı sıra.
        try:
            root.state("normal")
            root.deiconify()
            root.update_idletasks()
            root.attributes("-alpha", 1.0)
            root.lift()
            root.focus_force()
        except Exception:
            pass
        if callable(on_started):
            try:
                on_started(str(data.get("dil", "tr") or "tr"))
            except Exception:
                pass

    def animate(index):
        if state["done"]:
            return
        if index >= len(images):
            finish()
            return
        image = images[index]
        if image is not None:
            try:
                holder.configure(image=image)
            except Exception:
                pass
        delay = int(delays[index]) if index < len(delays) else 40
        state["job"] = win.after(max(18, delay), lambda: animate(index + 1))

    for sequence in ("<Button-1>", "<Key>", "<Escape>"):
        try:
            win.bind(sequence, finish)
        except Exception:
            pass
    try:
        win.focus_force()
    except Exception:
        pass

    # Güvenlik ağı: animasyon takılsa bile bu süre sonunda açılır.
    try:
        win.after(int(max(2.0, float(max_seconds)) * 1000), finish)
    except Exception:
        pass

    win.after(0, lambda: animate(0))
    return win


def run_launch_gate(
    root,
    get_asset_path,
    veri_yukle,
    veri_kaydet,
    dil_kaydet,
    on_started=None,
):
    """Show a non-blocking startup gate after the main UI has been constructed.

    This function never calls wait_window, wait_variable, update or a nested mainloop.
    The application's only event loop remains root.mainloop().
    """
    try:
        data = veri_yukle()
    except Exception:
        data = {}

    # ------------------------------------------------------------------
    # GİRİŞ EKRANI ATLAMA (v1.40 eklentisi — YALNIZCA EKLEME).
    # Ayarlarda "giris_ekrani_atla" true ise "Neto'ya Hoş Geldiniz /
    # Başlat" penceresi hiç oluşturulmaz; program doğrudan ana arayüzle
    # açılır. Ayar kapalıysa aşağıdaki mevcut akış birebir aynen çalışır.
    # ------------------------------------------------------------------
    try:
        if bool(data.get("giris_ekrani_atla", False)):
            try:
                print("[LAUNCH_GATE] giris ekrani atlandi (giris_ekrani_atla=true)", flush=True)
            except Exception:
                pass
            # Orijinal finish_reveal() dizisiyle aynı sıra: ana pencereyi
            # görünür kıl, sonra başlangıç geri çağrısını çalıştır.
            try:
                root.state("normal")
                root.deiconify()
                root.update_idletasks()
                root.lift()
                root.attributes("-alpha", 1.0)
                root.focus_force()
            except Exception:
                pass
            if callable(on_started):
                try:
                    on_started(str(data.get("dil", "tr") or "tr"))
                except Exception:
                    pass
            return None
    except Exception:
        pass

    # ------------------------------------------------------------------
    # LOGO ANİMASYONU + SES İLE AÇILIŞ (v1.40 eklentisi — YALNIZCA EKLEME).
    # "giris_logo_intro" true ise klasik "Başlat" kapısı hiç kurulmaz; logo
    # animasyonu ve ses biter bitmez ana arayüz kendiliğinden açılır.
    # Varlık dosyaları yoksa klasik kapı aynen çalışır.
    # ------------------------------------------------------------------
    try:
        if bool(data.get("giris_logo_intro", False)):
            logo_window = run_logo_intro(
                root,
                data,
                on_started=on_started,
                get_asset_path=get_asset_path,
            )
            if logo_window is not None:
                try:
                    print("[LAUNCH_GATE] logo animasyonu ile acilis", flush=True)
                except Exception:
                    pass
                return logo_window
            try:
                print("[LAUNCH_GATE] logo varligi bulunamadi, klasik kapiya donuldu", flush=True)
            except Exception:
                pass
    except Exception as _logo_error:
        try:
            print(f"[LOGO_INTRO_ERROR] {_logo_error}", flush=True)
        except Exception:
            pass

    current_lang = str(data.get("dil", "en") or "en").lower()
    if current_lang not in ("tr", "en"):
        current_lang = "en"

    state = {
        "lang": current_lang,
        "starting": False,
        "finished": False,
        "intro_running": False,
        "started_callback_done": False,
    }
    launch_started_at = time.perf_counter()
    watchdog_job = {"id": None}

    _quick_write_state(
        "ready.json",
        {
            "state": "gate_ready",
            "lang": current_lang,
            "timestamp": time.time(),
            "ready_seconds": 0.0,
        },
    )

    # Main root stays hidden until the fully-built UI is intentionally revealed.
    try:
        root.withdraw()
        root.attributes("-alpha", 1.0)
    except Exception:
        pass

    win = ctk.CTkToplevel(root)
    win.title(_texts(current_lang)["window"])
    win.geometry("570x460")
    win.resizable(False, False)
    win.configure(fg_color="#050509")
    set_window_icon(win, get_asset_path)
    center_window(win, 570, 460)

    try:
        win.attributes("-topmost", True)
    except Exception:
        pass

    try:
        win.protocol("WM_DELETE_WINDOW", lambda: None)
    except Exception:
        pass

    shell = ctk.CTkFrame(
        win,
        fg_color=GATE_COLORS["shell"],
        corner_radius=30,
        border_width=1,
        border_color=GATE_COLORS["border_soft"],
    )
    shell.pack(fill="both", expand=True, padx=15, pady=15)

    content = ctk.CTkFrame(shell, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=28, pady=22)

    live_var = ctk.BooleanVar(value=bool(data.get("start_live_mode_on_launch", False)))
    # v1.40: bu ekranı bir daha gösterme seçeneği (yalnızca ekleme).
    skip_var = ctk.BooleanVar(value=bool(data.get("giris_ekrani_atla", False)))

    def clear_content():
        for child in list(content.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    def save_preferences():
        try:
            dil_kaydet(state["lang"])
        except Exception:
            pass
        try:
            saved = veri_yukle()
            saved["dil"] = state["lang"]
            saved["start_live_mode_on_launch"] = bool(live_var.get())
            # v1.40: giriş ekranı tercihini de kaydet (yalnızca ekleme).
            saved["giris_ekrani_atla"] = bool(skip_var.get())
            veri_kaydet(saved)
        except Exception:
            pass

    def invoke_started_callback():
        """Run optional startup refreshes after the main window is visible."""
        if state["started_callback_done"]:
            return
        state["started_callback_done"] = True
        if not callable(on_started):
            return
        try:
            on_started(state["lang"])
        except TypeError:
            try:
                on_started()
            except Exception as exc:
                print(f"[LAUNCH_ON_STARTED_ERROR] {exc}", flush=True)
        except Exception as exc:
            print(f"[LAUNCH_ON_STARTED_ERROR] {exc}", flush=True)


    def reveal_main():
        if state["finished"]:
            return
        state["finished"] = True

        try:
            if watchdog_job.get("id"):
                win.after_cancel(watchdog_job["id"])
                watchdog_job["id"] = None
        except Exception:
            pass

        save_preferences()


        try:
            root.state("normal")
            root.deiconify()
            root.update_idletasks()
            root.lift()
        except Exception:
            pass

        reveal_state = {"done": False}

        def finish_reveal():
            if reveal_state["done"]:
                return
            reveal_state["done"] = True
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            try:
                root.attributes("-alpha", 1.0)
            except Exception:
                pass
            try:
                root.lift()
                root.focus_force()
            except Exception:
                pass
            try:
                payload = {
                    "state": "main_visible",
                    "lang": state["lang"],
                    "timestamp": time.time(),
                    "window_seconds": round(time.perf_counter() - launch_started_at, 3),
                }
                try:
                    payload["geometry"] = root.winfo_geometry()
                except Exception:
                    pass
                _quick_write_state("window.json", payload)
                _quick_write_state("shown.json", payload)
            except Exception:
                pass
            try:
                print(
                    f"[BOOT_GATE] main shown state={root.state()} "
                    f"viewable={root.winfo_viewable()} geometry={root.winfo_geometry()}",
                    flush=True,
                )
            except Exception:
                pass

        # The main window stays at its final size throughout the reveal.
        # Animate only the lightweight gate, then start optional UI refreshes.
        from neto_motion_engine_v2 import get_motion_engine
        def revealed():
            finish_reveal()
            root.after_idle(invoke_started_callback)
        try:
            get_motion_engine(root).fade_toplevel(
                win, start=1.0, end=0.0, duration_ms=180, on_complete=revealed)
        except Exception:
            revealed()

    def draw_loading():
        if state["starting"]:
            return
        state["starting"] = True
        try:
            watchdog_job["id"] = win.after(8000, reveal_main)
        except Exception:
            watchdog_job["id"] = None
        save_preferences()
        clear_content()
        texts = _texts(state["lang"])

        logo_image = load_logo_image(get_asset_path, (82, 82))
        logo = ctk.CTkLabel(content, text="" if logo_image else "N", image=logo_image,
                            font=("Segoe UI", 48, "bold"), text_color=GATE_COLORS["text"])
        if logo_image:
            setattr(logo, "image", logo_image)
        logo.pack(pady=(42, 12))

        ctk.CTkLabel(
            content,
            text=texts["starting"],
            text_color=GATE_COLORS["text"],
            font=("Segoe UI", 25, "bold"),
        ).pack(pady=(4, 8))

        status = ctk.CTkLabel(
            content,
            text=texts["ready"],
            text_color=GATE_COLORS["accent"],
            font=("Segoe UI", 13),
        )
        status.pack(pady=(0, 20))

        progress = ctk.CTkProgressBar(
            content,
            width=350,
            height=11,
            corner_radius=8,
            progress_color=GATE_COLORS["progress"],
            fg_color="#16213B",
        )
        progress.pack(pady=(0, 16))
        progress.set(0.35)

        progress_state = {"job": None, "value": 0.35}
        from neto_motion_engine_v2 import get_motion_engine
        progress_engine = get_motion_engine(win)

        def animate_progress(target, duration_ms=220, done=None):
            old = progress_state.get("job")
            if old:
                try:
                    progress_engine.cancel("launch-progress")
                except Exception:
                    pass
            start = float(progress_state.get("value", 0.0) or 0.0)
            target = _clamp(target)

            def update(value):
                if not win.winfo_exists():
                    progress_engine.cancel("launch-progress")
                    return
                progress_state["value"] = value
                try:
                    progress.set(value)
                except Exception:
                    return

            def finish():
                progress_state["job"] = None
                if callable(done):
                    done()

            progress_state["job"] = progress_engine.number(
                "launch-progress",
                start,
                target,
                update,
                duration_ms=duration_ms,
                easing="smootherstep",
                on_complete=finish,
            )

        # Short visual confirmation only. The main interface is already built,
        # therefore no resource loading runs here and the window cannot freeze.
        def stage_two():
            if not win.winfo_exists():
                return
            status.configure(text=texts["apply"])
            animate_progress(0.72, 210, lambda: win.after(45, stage_three))

        def stage_three():
            if not win.winfo_exists():
                return
            status.configure(text=texts["show"])

            def open_onboarding_or_reveal():
                try:
                    from neto_onboarding import show_onboarding_if_needed

                    shown = show_onboarding_if_needed(
                        win=win,
                        root=root,
                        get_asset_path=get_asset_path,
                        lang=state["lang"],
                        on_complete=reveal_main,
                    )
                    if shown:
                        return
                except Exception as onboarding_error:
                    try:
                        print(
                            f"[ONBOARDING_START_ERROR] {onboarding_error}",
                            flush=True,
                        )
                    except Exception:
                        pass
                reveal_main()

            animate_progress(1.0, 190, lambda: win.after(45, open_onboarding_or_reveal))

        win.after(70, stage_two)

    def draw_welcome():
        clear_content()
        texts = _texts(state["lang"])
        try:
            print("[BOOT_GATE] welcome visible", flush=True)
        except Exception:
            pass
        try:
            win.title(texts["window"])
        except Exception:
            pass

        logo_wrap = ctk.CTkFrame(
            content,
            width=112,
            height=112,
            corner_radius=56,
            fg_color=GATE_COLORS["card"],
            border_width=1,
            border_color=GATE_COLORS["border"],
        )
        logo_wrap.pack(pady=(8, 8))
        logo_wrap.pack_propagate(False)

        logo_image = load_logo_image(get_asset_path, (92, 92))
        logo = ctk.CTkLabel(logo_wrap, text="" if logo_image else "N", image=logo_image,
                            font=("Segoe UI", 54, "bold"), text_color=GATE_COLORS["text"])
        if logo_image:
            setattr(logo, "image", logo_image)
        logo.pack(expand=True)

        # Giriş ekranında iki kısa tur atan, düşük maliyetli logo halkası animasyonu.
        def pulse_logo(step=0):
            if not logo_wrap.winfo_exists() or state.get("starting"):
                return
            amount = (math.sin(step * 0.22) + 1.0) / 2.0
            dark = (19, 30, 58)
            accent = (104, 167, 255)
            rgb = tuple(round(a + (b - a) * amount) for a, b in zip(dark, accent))
            try:
                logo_wrap.configure(
                    border_color="#%02X%02X%02X" % rgb,
                    border_width=2 if amount > 0.52 else 1,
                    fg_color="#%02X%02X%02X" % tuple(round(a + (b - a) * (amount * 0.35)) for a, b in zip((14, 23, 46), accent)),
                )
            except Exception:
                return
            if step < 64:
                win.after(20, lambda: pulse_logo(step + 1))

        win.after(80, pulse_logo)

        ctk.CTkLabel(
            content,
            text=texts["title"],
            text_color=GATE_COLORS["text"],
            font=("Segoe UI", 26, "bold"),
        ).pack(pady=(0, 5))
        ctk.CTkLabel(
            content,
            text=texts["description"],
            text_color=GATE_COLORS["text_dim"],
            font=("Segoe UI", 13),
            wraplength=460,
        ).pack(pady=(0, 18))

        lang_row = ctk.CTkFrame(content, fg_color="transparent")
        lang_row.pack(pady=(0, 15))

        def choose_language(lang):
            if state["starting"]:
                return
            state["lang"] = lang
            save_preferences()
            draw_welcome()

        for code, text in (("tr", "Türkçe"), ("en", "English")):
            selected = state["lang"] == code
            ctk.CTkButton(
                lang_row,
                text=text,
                width=150,
                height=42,
                corner_radius=16,
                fg_color=GATE_COLORS["accent"] if selected else GATE_COLORS["card_soft"],
                hover_color=GATE_COLORS["accent_hover"] if selected else "#1A2344",
                text_color="#08111B" if selected else "#ffffff",
                command=lambda selected_code=code: choose_language(selected_code),
            ).pack(side="left", padx=7)

        ctk.CTkCheckBox(
            content,
            text=texts["live"],
            variable=live_var,
            text_color=GATE_COLORS["text_dim"],
            fg_color=GATE_COLORS["accent"],
            hover_color=GATE_COLORS["accent_hover"],
            border_color=GATE_COLORS["border_soft"],
            checkbox_width=20,
            checkbox_height=20,
        ).pack(pady=(2, 6))

        # v1.40: giriş ekranını kalıcı olarak atlama seçeneği (yalnızca ekleme).
        ctk.CTkCheckBox(
            content,
            text=("Bu ekranı bir daha gösterme" if str(state.get("lang")) == "tr"
                  else "Do not show this screen again"),
            variable=skip_var,
            text_color=GATE_COLORS["text_dim"],
            fg_color=GATE_COLORS["accent"],
            hover_color=GATE_COLORS["accent_hover"],
            border_color=GATE_COLORS["border_soft"],
            checkbox_width=20,
            checkbox_height=20,
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            content,
            text=texts["hint"],
            text_color=GATE_COLORS["text_dim"],
            font=("Segoe UI", 11),
            wraplength=450,
        ).pack(pady=(0, 15))

        ctk.CTkButton(
            content,
            text=texts["start"],
            width=190,
            height=46,
            corner_radius=22,
            fg_color="#F7FBFF",
            hover_color="#DCEAFF",
            text_color="#101824",
            font=("Segoe UI", 14, "bold"),
            command=draw_loading,
        ).pack()

    def draw_intro():
        clear_content()
        texts = _texts(state["lang"])
        try:
            print("[BOOT_GATE] intro visible", flush=True)
        except Exception:
            pass
        try:
            win.title(texts["window"])
        except Exception:
            pass

        intro_card = ctk.CTkFrame(
            content,
            fg_color=GATE_COLORS["card"],
            corner_radius=28,
            border_width=1,
            border_color=GATE_COLORS["border_soft"],
        )
        intro_card.pack(fill="both", expand=True, padx=24, pady=18)

        intro_inner = ctk.CTkFrame(intro_card, fg_color="transparent")
        intro_inner.pack(fill="both", expand=True, padx=28, pady=22)

        intro_image_holder = ctk.CTkFrame(
            intro_inner,
            fg_color=GATE_COLORS["bg"],
            corner_radius=22,
            border_width=1,
            border_color=GATE_COLORS["border_soft"],
        )
        intro_image_holder.pack(pady=(8, 14))

        intro_image_label = ctk.CTkLabel(intro_image_holder, text="")
        intro_image_label.pack(padx=16, pady=16)

        intro_title = ctk.CTkLabel(
            intro_inner,
            text=texts["intro_title"],
            font=("Segoe UI Semibold", 25),
            text_color=GATE_COLORS["text"],
        )
        intro_title.pack(pady=(0, 2))

        intro_status = ctk.CTkLabel(
            intro_inner,
            text=texts["intro_status"],
            font=("Segoe UI", 13),
            text_color=GATE_COLORS["text_dim"],
        )
        intro_status.pack(pady=(0, 12))

        intro_bar = ctk.CTkProgressBar(
            intro_inner,
            width=260,
            height=10,
            corner_radius=7,
            fg_color="#17213B",
            progress_color=GATE_COLORS["progress"],
        )
        intro_bar.pack(pady=(0, 2))
        intro_bar.set(0.12)

        frames, delays, _intro_asset = load_intro_animation(get_asset_path, (320, 320))
        if not frames:
            draw_welcome()
            return

        intro_images = [
            ctk.CTkImage(light_image=frame, dark_image=frame, size=frame.size)
            for frame in frames
        ]
        state["intro_running"] = True
        state["intro_frames"] = frames
        state["intro_images"] = intro_images
        pulse_state = {"step": 0}

        def pulse_intro_holder():
            if (
                not win.winfo_exists()
                or state.get("starting")
                or state.get("finished")
                or not state.get("intro_running")
            ):
                return
            pulse_state["step"] += 1
            amount = (math.sin(pulse_state["step"] * 0.18) + 1.0) / 2.0
            try:
                intro_image_holder.configure(
                    border_color=_mix_hex_color(GATE_COLORS["border_soft"], GATE_COLORS["accent"], amount),
                    fg_color=_mix_hex_color(GATE_COLORS["bg"], GATE_COLORS["card"], amount * 0.22),
                    border_width=2 if amount > 0.55 else 1,
                )
            except Exception:
                return
            try:
                win.after(28, pulse_intro_holder)
            except Exception:
                pass

        def finish_intro():
            if not win.winfo_exists() or state.get("starting") or state.get("finished"):
                return
            state["intro_running"] = False
            state["intro_frames"] = []
            state["intro_images"] = []
            try:
                intro_bar.set(1.0)
            except Exception:
                pass
            draw_welcome()

        def animate(index=0):
            if not win.winfo_exists() or state.get("starting") or state.get("finished"):
                return
            if index >= len(frames):
                win.after(120, finish_intro)
                return
            frame = frames[index]
            delay = delays[index] if index < len(delays) else 35
            try:
                photo = intro_images[index] if index < len(intro_images) else ctk.CTkImage(
                    light_image=frame,
                    dark_image=frame,
                    size=frame.size,
                )
                intro_image_label.configure(image=photo)
                setattr(intro_image_label, "image", photo)
                setattr(intro_image_label, "_neto_intro_frame", photo)
            except Exception:
                finish_intro()
                return
            try:
                intro_bar.set(min(0.96, (index + 1) / max(1, len(frames))))
            except Exception:
                pass
            if index < len(frames) - 1:
                win.after(delay, lambda: animate(index + 1))
            else:
                win.after(max(120, delay), finish_intro)

        try:
            win.after(28, pulse_intro_holder)
            win.after(0, animate)
        except Exception:
            finish_intro()

    draw_intro()

    # Mapping/grab happens after the one real mainloop starts.
    def activate_gate():
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
            win.grab_set()
        except Exception:
            pass
        try:
            print("[BOOT_GATE] startup visible", flush=True)
        except Exception:
            pass

    win.after_idle(activate_gate)
    return win
