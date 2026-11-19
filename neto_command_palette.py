from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk

import customtkinter as ctk

from neto_runtime_core import PROFILE_LABELS, get_runtime
from neto_branding import add_header_logo, apply_window_icon, get_ctk_image
from neto_feature_gate import require_feature


_WINDOW = None


def _safe_call(namespace, name, *args, **kwargs):
    callback = namespace.get(name) if isinstance(namespace, dict) else None
    if callable(callback):
        return callback(*args, **kwargs)
    return None


def _palette_state_load(namespace):
    state = {"recent": [], "favorites": []}
    try:
        data = _safe_call(namespace, "veri_yukle")
        if isinstance(data, dict):
            recent = data.get("command_palette_recent", [])
            favorites = data.get("command_palette_favorites", [])
            if isinstance(recent, (list, tuple)):
                state["recent"] = [str(item) for item in recent if str(item).strip()]
            if isinstance(favorites, (list, tuple)):
                state["favorites"] = [str(item) for item in favorites if str(item).strip()]
    except Exception:
        pass
    # Favoriler ve son kullanılanlar için makul küçük limitler.
    state["recent"] = state["recent"][:12]
    state["favorites"] = state["favorites"][:20]
    return state


def _palette_state_save(namespace, state):
    try:
        data = _safe_call(namespace, "veri_yukle")
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    try:
        data["command_palette_recent"] = list(state.get("recent") or [])[:12]
        data["command_palette_favorites"] = list(state.get("favorites") or [])[:20]
        _safe_call(namespace, "veri_kaydet", data)
        return True
    except Exception:
        return False


def _profile_command(profile):
    runtime = get_runtime()
    return lambda: runtime.set_profile(profile)


def _linux_bridge_toggle(enabled):
    def worker():
        try:
            runtime = get_runtime()
            runtime.set_custom_feature("linux_bridge", bool(enabled))
        except Exception:
            pass

    threading.Thread(
        target=worker,
        daemon=True,
        name=f"NetOpsLinuxBridge{'Enable' if enabled else 'Disable'}",
    ).start()


def _open_wsl_shell():
    try:
        import neto_wsl_bridge

        snapshot = neto_wsl_bridge.status()
        if not snapshot.get("available") or not snapshot.get("distros"):
            return False
        return bool(neto_wsl_bridge.open_wsl_shell())
    except Exception:
        return False


def _virtual_desktop_action(action: str):
    """Run one fixed virtual-desktop action without accepting raw QEMU args."""
    try:
        import neto_virtual_desktop

        result = neto_virtual_desktop.handle_command(f"sanal masaustu {action}")
        return result or {"ok": False, "state": "ignored", "message": "Sanal masaustu komutu taninmadi."}
    except Exception as exc:
        return {"ok": False, "state": "error", "message": f"Sanal masaustu kullanilamadi: {exc}"}


def _commands(namespace):
    runtime = get_runtime()
    project = Path(namespace.get("__file__", Path.cwd())).resolve().parent

    commands = [
        {
            "id": "power_center",
            "title": "NetOps Güç Merkezi'ni aç",
            "keywords": "power center güç merkezi açık kaynak araçlar entegrasyon",
            "action": lambda: __import__("neto_power_features").open_power_center(runtime.root, namespace),
        },
        {
            "id": "quick_actions",
            "title": "Hızlı İşlemler",
            "keywords": "quick actions hızlı işlemler yardımcı araçlar",
            "action": lambda: _safe_call(namespace, "neto_quick_actions_penceresi_ac"),
        },
        {
            "id": "v10_pulse",
            "title": "NetOps v10 Pulse merkezini aç",
            "keywords": "v10 pulse sağlık durum sürüm driver sürücü rollback geri al",
            "action": lambda: _safe_call(namespace, "neto_v10_pulse_ac"),
        },
        {
            "id": "settings_system",
            "title": "Ayarlar · Sistem ve Performans",
            "keywords": "ayarlar sistem performans profil services",
            "action": lambda: _safe_call(namespace, "ayarlar_sayfasi_ac", "system"),
        },
        {
            "id": "settings_appearance",
            "title": "Ayarlar · Görünüm",
            "keywords": "ayarlar görünüm tema appearance ui",
            "action": lambda: _safe_call(namespace, "ayarlar_sayfasi_ac", "appearance"),
        },
        {
            "id": "live_mode",
            "title": "Live Mode'u aç",
            "keywords": "live mikrofon ses",
            "action": lambda: _safe_call(namespace, "inline_live_start"),
        },
        {
            "id": "now_playing",
            "title": "Şimdi Çalıyor'u aç",
            "keywords": "now playing müzik media",
            "action": lambda: _safe_call(namespace, "now_playing_manual_open", True),
        },
        {
            "id": "device_hub_center",
            "title": "Cihaz bağla / QR merkezini aç",
            "keywords": "android cihaz bağla qr pairing adb device",
            "action": lambda: _safe_call(namespace, "neto_device_hub_ac_safe"),
        },
        {
            "id": "linux_bridge_enable",
            "title": "Linux köprüsünü etkinleştir",
            "keywords": "linux wsl bridge kernel",
            "action": lambda: _linux_bridge_toggle(True),
        },
        {
            "id": "linux_bridge_disable",
            "title": "Linux köprüsünü kapat",
            "keywords": "linux wsl bridge kapat stop",
            "action": lambda: _linux_bridge_toggle(False),
        },
        {
            "id": "open_wsl_shell",
            "title": "WSL kabuğunu aç",
            "keywords": "linux wsl shell terminal bash",
            "action": _open_wsl_shell,
        },
        {
            "id": "virtual_desktop_start",
            "title": "Sanal masaüstünü başlat",
            "keywords": "qemu sanal masaüstü sanal masaustu casrev linux",
            "action": lambda: _virtual_desktop_action("baslat"),
        },
        {
            "id": "virtual_desktop_status",
            "title": "Sanal masaüstü durumunu göster",
            "keywords": "qemu sanal masaüstü durum status",
            "action": lambda: _virtual_desktop_action("durumu"),
        },
        {
            "id": "virtual_desktop_stop",
            "title": "Sanal masaüstünü durdur",
            "keywords": "qemu sanal masaüstü durdur kapat",
            "action": lambda: _virtual_desktop_action("durdur"),
        },
        {
            "id": "device_hub",
            "title": "Cihazlar sekmesini aç",
            "keywords": "cihazlar device hub pairing agent websocket android cihaz merkezi",
            "action": lambda: _safe_call(namespace, "neto_device_hub_ac_safe"),
        },
        {
            "id": "check_updates",
            "title": "Güncellemeleri kontrol et",
            "keywords": "update updater güncelle",
            "action": lambda: require_feature(
                root=runtime.root,
                feature="updater",
                action=lambda: runtime.services.start("updater"),
                lang="tr",
            ),
        },
        {
            "id": "run_doctor",
            "title": "NetOps Doktor'u çalıştır",
            "keywords": "doctor doktor teşhis diagnostics",
            "action": lambda: _run_doctor(project),
        },
        {
            "id": "open_project_folder",
            "title": "Proje klasörünü aç",
            "keywords": "folder klasör project",
            "action": lambda: _open_path(project),
        },
        {
            "id": "toast_test",
            "title": "Bildirim testi göster",
            "keywords": "toast bildirim test success info",
            "action": lambda: _safe_call(namespace, "neto_toast_goster", "NetOps", "Toast sistemi çalışıyor.", "success"),
        },
        {
            "id": "open_logs",
            "title": "Log penceresini aç",
            "keywords": "log logs hata crash debug",
            "action": lambda: _safe_call(namespace, "neto_log_penceresi_ac"),
        },
        {
            "id": "open_log_folder",
            "title": "Log klasörünü aç",
            "keywords": "log folder klasör logs",
            "action": lambda: _safe_call(namespace, "neto_logs_klasorunu_ac"),
        },
        {
            "id": "power_center_status",
            "title": "NetOps Güç Merkezi durumunu göster",
            "keywords": "powertoys flow launcher kde connect localsend syncthing espanso obs keepass rustdesk güç merkezi araçlar",
            "action": lambda: _power_feature_action(namespace, "status"),
        },
        {
            "id": "capture_screen",
            "title": "Ekran görüntüsü al",
            "keywords": "sharex screenshot ekran görüntüsü capture ocr",
            "action": lambda: _power_feature_action(namespace, "capture"),
        },
        {
            "id": "activity_summary",
            "title": "Yerel aktivite özetini göster",
            "keywords": "activitywatch aktivite kullanım istatistik süre",
            "action": lambda: _power_feature_action(namespace, "activity"),
        },
    ]

    for app_id, title, keywords in (
        ("flow_launcher", "Flow Launcher'ı aç", "flow launcher hızlı arama"),
        ("powertoys", "PowerToys'u aç", "powertoys pencere araçları"),
        ("kde_connect", "KDE Connect'i aç", "kde connect telefon bildirim pano"),
        ("localsend", "LocalSend'i aç", "localsend dosya gönder"),
        ("syncthing", "Syncthing'i aç", "syncthing senkronizasyon"),
        ("espanso", "Espanso'yu aç", "espanso metin şablonu"),
        ("obs", "OBS Studio'yu aç", "obs ekran kayıt yayın"),
        ("keepassxc", "KeePassXC'yi aç", "keepassxc şifre kasa"),
        ("rustdesk", "RustDesk'i aç", "rustdesk uzak destek"),
    ):
        commands.append({
            "id": f"open_{app_id}",
            "title": title,
            "keywords": keywords,
            "action": lambda current=app_id: _power_feature_action(namespace, "open_app", app_id=current),
        })

    for profile in ("force_fast", "fast", "balanced", "full"):
        commands.append({
            "id": f"profile_{profile}",
            "title": f"Performans profili: {PROFILE_LABELS[profile]['tr']}",
            "keywords": f"profile performans {profile}",
            "action": _profile_command(profile),
        })

    return commands


def _open_path(path):
    path = Path(path)
    try:
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _run_doctor(project):
    doctor = Path(project) / "neto_doctor.py"
    if not doctor.is_file():
        return
    try:
        subprocess.Popen([sys.executable, str(doctor), "--project", str(project)], cwd=str(project))
    except Exception:
        pass


def _power_feature_action(namespace, action: str, *, app_id: str = ""):
    """Run one allowlisted power feature and report a compact result."""
    try:
        import neto_power_features as power

        if action == "status":
            report = power.status_report()
            installed = sum(1 for item in report["integrations"] if item.get("installed"))
            _safe_call(namespace, "neto_toast_goster", "NetOps Güç Merkezi", f"{installed} dış araç algılandı; yerel özellikler hazır.", "info")
            return report
        if action == "capture":
            result = power.capture_screen()
            message = result.get("path") if result.get("ok") else result.get("error", "Ekran yakalanamadı.")
            _safe_call(namespace, "neto_toast_goster", "Ekran Yakalama", str(message), "success" if result.get("ok") else "error")
            return result
        if action == "activity":
            summary = power.activity_summary()
            message = "Aktivite kaydı kapalı." if not summary else f"{len(summary)} yerel aktivite grubu bulundu."
            _safe_call(namespace, "neto_toast_goster", "Aktivite Özeti", message, "info")
            return summary
        if action == "open_app":
            result = power.open_optional_app(app_id)
            _safe_call(namespace, "neto_toast_goster", "NetOps Entegrasyonu", result.get("error", "Uygulama açılıyor."), "success" if result.get("ok") else "info")
            return result
    except Exception as exc:
        _safe_call(namespace, "neto_toast_goster", "NetOps Güç Merkezi", str(exc), "error")
    return None


def open_command_palette(root, namespace):
    global _WINDOW

    try:
        if _WINDOW is not None and _WINDOW.winfo_exists():
            _WINDOW.deiconify()
            _WINDOW.lift()
            _WINDOW.focus_force()
            return _WINDOW
    except Exception:
        _WINDOW = None

    window = ctk.CTkToplevel(root)
    _WINDOW = window
    window.title("NetOps Komut Paleti")
    apply_window_icon(window)
    window.geometry("680x480")
    window.minsize(520, 360)
    window.configure(fg_color="#0B0B0F")
    try:
        window.transient(root)
        window.attributes("-topmost", True)
        window.after(600, lambda: window.attributes("-topmost", False))
    except Exception:
        pass

    shell = ctk.CTkFrame(
        window,
        fg_color="#17171D",
        border_width=1,
        border_color="#34343D",
        corner_radius=16,
    )
    shell.pack(fill="both", expand=True, padx=14, pady=14)

    header = ctk.CTkFrame(shell, fg_color="transparent", height=58)
    header.pack(fill="x", padx=16, pady=(10, 2))
    header.pack_propagate(False)

    logo_image = get_ctk_image(40)
    ctk.CTkLabel(
        header,
        text="",
        image=logo_image,
        width=44,
        height=44,
        fg_color="transparent",
    ).pack(side="left", padx=(0, 11), pady=7)

    ctk.CTkLabel(
        header,
        text="Komut Paleti",
        text_color="#F4F4F5",
        font=("Segoe UI Semibold", 20),
        anchor="w",
    ).pack(side="left", fill="x", expand=True, pady=7)

    entry = ctk.CTkEntry(
        shell,
        placeholder_text="Komut ara…",
        height=40,
        fg_color="#101015",
        border_color="#3F3F49",
        text_color="#F4F4F5",
        font=("Segoe UI", 12),
    )
    entry.pack(fill="x", padx=16, pady=(4, 10))

    list_frame = ctk.CTkScrollableFrame(
        shell,
        fg_color="#101015",
        corner_radius=12,
        scrollbar_button_color="#34343D",
        scrollbar_button_hover_color="#454550",
    )
    list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    all_commands = _commands(namespace)
    command_index = {str(command.get("id", "")): command for command in all_commands if str(command.get("id", "")).strip()}
    command_order = {str(command.get("id", "")): idx for idx, command in enumerate(all_commands) if str(command.get("id", "")).strip()}
    palette_state = _palette_state_load(namespace)
    recent_ids = [cid for cid in palette_state.get("recent", []) if cid in command_index]
    favorite_ids = [cid for cid in palette_state.get("favorites", []) if cid in command_index]
    favorite_set = set(favorite_ids)

    command_rows = []
    visible_commands = []
    selected_index = -1

    def _save_palette_state():
        palette_state["recent"] = recent_ids[:12]
        palette_state["favorites"] = favorite_ids[:20]
        _palette_state_save(namespace, palette_state)

    def close():
        global _WINDOW
        _WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    def record_recent(command_id):
        nonlocal recent_ids
        command_id = str(command_id or "").strip()
        if not command_id:
            return
        recent_ids = [command_id] + [cid for cid in recent_ids if cid != command_id and cid in command_index]
        recent_ids = recent_ids[:12]
        _save_palette_state()

    def toggle_favorite(command_id):
        nonlocal favorite_ids, favorite_set
        command_id = str(command_id or "").strip()
        if not command_id:
            return
        if command_id in favorite_set:
            favorite_ids = [cid for cid in favorite_ids if cid != command_id]
        else:
            favorite_ids = [command_id] + [cid for cid in favorite_ids if cid in command_index and cid != command_id]
        favorite_ids = favorite_ids[:20]
        favorite_set = set(favorite_ids)
        _save_palette_state()
        render()

    def execute(command):
        try:
            record_recent(command.get("id", ""))
            command["action"]()
        finally:
            close()

    def select(index, focus=False):
        nonlocal selected_index
        if not command_rows:
            selected_index = -1
            return
        selected_index = max(0, min(int(index), len(command_rows) - 1))
        for idx, row in enumerate(command_rows):
            selected = idx == selected_index
            try:
                row["frame"].configure(fg_color="#24242D" if selected else "transparent")
            except Exception:
                pass
            try:
                row["action"].configure(
                    fg_color="#24242D" if selected else "transparent",
                    hover_color="#2F2F3A" if selected else "#282831",
                    text_color="#FFFFFF" if selected else "#F4F4F5",
                )
            except Exception:
                pass
        if focus:
            try:
                entry.focus_set()
            except Exception:
                pass

    def move_selection(delta):
        if not command_rows:
            return "break"
        next_index = 0 if selected_index < 0 else selected_index + int(delta)
        if next_index < 0:
            next_index = len(command_rows) - 1
        elif next_index >= len(command_rows):
            next_index = 0
        select(next_index)
        return "break"

    def activate_selected(_event=None):
        if 0 <= selected_index < len(visible_commands):
            execute(visible_commands[selected_index])
        return "break"

    def _clear_results():
        nonlocal command_rows, visible_commands, selected_index
        for child in list(list_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        command_rows = []
        visible_commands = []
        selected_index = -1

    def _heading(text):
        label = ctk.CTkLabel(
            list_frame,
            text=text,
            text_color="#A1A1AA",
            font=("Segoe UI Semibold", 10),
            anchor="w",
        )
        label.pack(fill="x", padx=8, pady=(12, 4))
        return label

    def _row_for(command):
        cmd_id = str(command.get("id", "")).strip()
        row = ctk.CTkFrame(list_frame, fg_color="transparent", corner_radius=10)
        row.pack(fill="x", padx=4, pady=2)

        star = ctk.CTkButton(
            row,
            text="★" if cmd_id in favorite_set else "☆",
            width=34,
            height=34,
            corner_radius=9,
            fg_color="#23232B" if cmd_id in favorite_set else "#1A1A21",
            hover_color="#2D2D36",
            text_color="#FBBF24" if cmd_id in favorite_set else "#A1A1AA",
            font=("Segoe UI Semibold", 12),
            command=lambda cid=cmd_id: toggle_favorite(cid),
        )
        star.pack(side="left", padx=(0, 6))

        action = ctk.CTkButton(
            row,
            text=command["title"],
            height=39,
            anchor="w",
            corner_radius=9,
            fg_color="transparent",
            hover_color="#282831",
            text_color="#F4F4F5",
            font=("Segoe UI Semibold", 11),
            command=lambda current=command: execute(current),
        )
        action.pack(side="left", fill="x", expand=True)

        idx = len(command_rows)
        row.bind("<Enter>", lambda _event, i=idx: select(i))
        action.bind("<Enter>", lambda _event, i=idx: select(i))
        star.bind("<Enter>", lambda _event, i=idx: select(i))

        command_rows.append({"frame": row, "action": action, "star": star, "command": command})
        visible_commands.append(command)

    def render(*_args):
        nonlocal recent_ids, favorite_ids, favorite_set
        query = entry.get().strip().casefold()
        _clear_results()

        if query:
            matched = []
            for command in all_commands:
                haystack = f"{command['title']} {command.get('keywords', '')}".casefold()
                if query in haystack:
                    matched.append(command)
            matched.sort(
                key=lambda command: (
                    0 if str(command.get("id", "")) in favorite_set else 1,
                    0 if str(command.get("id", "")) in set(recent_ids) else 1,
                    command_order.get(str(command.get("id", "")), 999),
                )
            )
            for command in matched:
                _row_for(command)
        else:
            shown_ids = set()
            favorite_commands = [command_index[cid] for cid in favorite_ids if cid in command_index]
            recent_commands = [command_index[cid] for cid in recent_ids if cid in command_index and cid not in favorite_set]
            other_commands = [
                command for command in all_commands
                if str(command.get("id", "")) not in favorite_set
                and str(command.get("id", "")) not in set(recent_ids)
            ]

            if favorite_commands:
                _heading("Favoriler")
                for command in favorite_commands:
                    shown_ids.add(str(command.get("id", "")))
                    _row_for(command)

            if recent_commands:
                _heading("Son Kullanılanlar")
                for command in recent_commands:
                    if str(command.get("id", "")) in shown_ids:
                        continue
                    shown_ids.add(str(command.get("id", "")))
                    _row_for(command)

            if other_commands:
                _heading("Tüm Komutlar")
                for command in other_commands:
                    if str(command.get("id", "")) in shown_ids:
                        continue
                    shown_ids.add(str(command.get("id", "")))
                    _row_for(command)

            if not command_rows:
                label = ctk.CTkLabel(
                    list_frame,
                    text="Eşleşen komut bulunamadı.",
                    text_color="#A1A1AA",
                    font=("Segoe UI", 11),
                )
                label.pack(pady=25)

        if command_rows:
            select(0)

    def on_key_release(event):
        if event.keysym in {"Up", "Down", "Return", "Escape", "Left", "Right", "Home", "End", "Prior", "Next"}:
            return
        if not event.char and event.keysym not in {"BackSpace", "Delete"}:
            return
        render()

    entry.bind("<KeyRelease>", on_key_release)
    entry.bind("<Down>", move_selection)
    entry.bind("<Up>", lambda _event: move_selection(-1))
    entry.bind("<Return>", activate_selected)
    entry.bind("<Escape>", lambda _event: close())
    window.bind("<Escape>", lambda _event: close())
    window.protocol("WM_DELETE_WINDOW", close)
    render()
    entry.focus_set()
    return window


def bind_command_palette(root, namespace):
    if root is None:
        return False

    def open_palette(_event=None):
        open_command_palette(root, namespace)
        return "break"

    try:
        root.bind_all("<Control-k>", open_palette)
        root.bind_all("<Control-K>", open_palette)
        root.bind_all("<Control-Shift-P>", open_palette)
        return True
    except Exception:
        return False
