from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Optional

import customtkinter as ctk

from neto_automation_core import (
    ACTION_TYPES,
    AUTOMATION_BUILD,
    TRIGGER_TYPES,
    AutomationDefinition,
    AutomationError,
    ValidationError,
    create_automation,
    delete_automation,
    get_automation,
    get_required_permissions,
    list_automations,
    list_events,
    list_runs,
    preview_automation,
    profile_allows_panel,
    profile_allows_scheduler,
    rollback_run,
    run_in_subprocess,
    set_enabled,
    start_worker,
    stop_worker,
    update_automation,
    worker_status,
)
from neto_automation_backup import export_bundle, import_bundle
from neto_automation_guard import (
    clear_emergency_stop,
    dry_run,
    emergency_status,
    emergency_stop_all,
    health_check,
    history,
)

try:
    from neto_branding import apply_window_icon as _neto_apply_window_icon, get_ctk_image as _neto_get_ctk_image
except Exception:
    _neto_apply_window_icon = None
    _neto_get_ctk_image = None


def apply_window_icon(*args, **kwargs) -> bool:
    func = _neto_apply_window_icon
    if callable(func):
        return bool(func(*args, **kwargs))
    return False


def get_ctk_image(*args, **kwargs):
    func = _neto_get_ctk_image
    if callable(func):
        return func(*args, **kwargs)
    return None


TRIGGER_LABELS = {
    "manual": "Manuel",
    "interval": "Belirli aralık",
    "daily": "Her gün / seçili günler",
    "startup": "Neto açıldığında",
    "file_change": "Dosya veya klasör değişince",
    "internet_online": "İnternet geri gelince",
    "resource_threshold": "CPU / RAM / disk eşiği",
    "process_open": "Program açıldığında",
}

ACTION_LABELS = {
    "notify": "Bildirim göster",
    "run_program": "Program çalıştır",
    "run_command": "PowerShell / komut çalıştır",
    "open_url": "Web adresi aç",
    "copy_file": "Dosya veya klasör kopyala",
    "move_file": "Dosya veya klasör taşı",
    "backup_folder": "Klasörü ZIP olarak yedekle",
    "http_request": "HTTP isteği gönder",
    "public_api_watch": "Public API izle",
    "wait": "Bekle",
    "write_text": "Dosyaya metin yaz",
    "lua_script": "Lua scripti çalıştır",
    "shutdown": "Bilgisayarı kapat",
    "run_scene": "Neto Hazırla sahnesi çalıştır",
}

PERMISSION_LABELS = {
    "notification": "Bildirim",
    "process": "Program / komut çalıştırma",
    "network": "Ağ erişimi",
    "file_read": "Dosya okuma",
    "file_write": "Dosya yazma",
}


class Palette:
    def __init__(self, getter: Optional[Callable[[], dict[str, str]]]):
        value = getter() if callable(getter) else {}
        self.bg = value.get("bg", "#0B0B0F")
        self.sidebar = value.get("sidebar", "#111116")
        self.card = value.get("card", "#19191F")
        self.card_2 = value.get("entry_bg", "#101015")
        self.border = value.get("entry_border", "#35353F")
        self.text = value.get("text_main", "#F4F4F5")
        self.muted = value.get("text_dim", "#A1A1AA")
        self.accent = value.get("neon", "#22C55E")
        self.hover = value.get("button_hover", "#292932")
        self.red = "#EF4444"
        self.yellow = "#F59E0B"
        self.blue = "#3B82F6"


def format_ts(value: Optional[float]) -> str:
    if not value:
        return "—"
    return dt.datetime.fromtimestamp(value).strftime("%d.%m.%Y %H:%M:%S")


def trigger_summary(trigger_type: str, trigger: dict[str, Any]) -> str:
    if trigger_type == "manual":
        return "Yalnızca kullanıcı çalıştırdığında"
    if trigger_type == "interval":
        return f"Her {trigger.get('seconds', 0)} saniyede"
    if trigger_type == "daily":
        weekdays = trigger.get("weekdays", [])
        labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        day_text = ", ".join(labels[index] for index in weekdays if 0 <= index < 7)
        return f"{trigger.get('time', '00:00')} · {day_text}"
    if trigger_type == "startup":
        return f"Açılıştan {trigger.get('delay_seconds', 0)} saniye sonra"
    if trigger_type == "file_change":
        return f"Değişiklik: {trigger.get('path', '')}"
    if trigger_type == "internet_online":
        return f"İnternet geri gelince · {trigger.get('host', '1.1.1.1')}:{trigger.get('port', 53)}"
    if trigger_type == "resource_threshold":
        return (
            f"{str(trigger.get('metric', 'cpu')).upper()} "
            f"{trigger.get('operator', '>=')} %{trigger.get('threshold', 85)}"
        )
    return trigger_type


def action_summary(action: dict[str, Any]) -> str:
    action_type = action.get("type", "")
    label = ACTION_LABELS.get(action_type, action_type)
    if action_type == "notify":
        return f"{label}: {action.get('message', '')[:80]}"
    if action_type == "run_program":
        return f"{label}: {action.get('path', '')}"
    if action_type == "run_command":
        return f"{label}: {action.get('command', '')[:90]}"
    if action_type == "open_url":
        return f"{label}: {action.get('url', '')}"
    if action_type in {"copy_file", "move_file"}:
        return f"{label}: {action.get('source', '')} -> {action.get('destination', '')}"
    if action_type == "backup_folder":
        return f"{label}: {action.get('source', '')}"
    if action_type == "http_request":
        return f"{label}: {action.get('method', 'GET')} {action.get('url', '')}"
    if action_type == "public_api_watch":
        return f"{label}: {action.get('api_label') or action.get('api', '')}"
    if action_type == "wait":
        return f"{label}: {action.get('seconds', 0)} saniye"
    if action_type == "shutdown":
        return f"{label}: {action.get('delay_seconds', 30)} sn sonra"
    if action_type == "write_text":
        return f"{label}: {action.get('path', '')}"
    if action_type == "lua_script":
        return f"{label}: Lua otomasyon kodu"
    if action_type == "run_scene":
        return f"{label}: {action.get('scene_id', '')}"
    return str(label or action_type)

class AutomationPanel:
    def __init__(
        self,
        parent,
        *,
        root=None,
        palette_getter: Optional[Callable[[], dict[str, str]]] = None,
        close_command: Optional[Callable[[], None]] = None,
    ):
        self.parent = parent
        self.root = root or parent.winfo_toplevel()
        self.close_command = close_command
        self.palette = Palette(palette_getter)
        self.selected_id: Optional[str] = None
        self.refresh_job = None
        self.closed = False
        self.last_worker_alive: Optional[bool] = None
        self._editors: list[Any] = []
        self._active_editor: Optional[Any] = None
        self.cards: dict[str, Any] = {}

        self.frame = ctk.CTkFrame(parent, fg_color=self.palette.bg, corner_radius=0)
        self.frame.pack(fill="both", expand=True)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._configure_ttk()
        self._build_header()
        self._build_body()
        self.refresh_all()
        self._refresh_loop()

        if profile_allows_scheduler():
            threading.Thread(target=start_worker, daemon=True, name="NetoAutomationWorkerStart").start()

    def widget(self):
        return self.frame

    def _configure_ttk(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Automation.Treeview",
            background=self.palette.card_2,
            fieldbackground=self.palette.card_2,
            foreground=self.palette.text,
            rowheight=27,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Automation.Treeview.Heading",
            background=self.palette.card,
            foreground=self.palette.text,
            relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Automation.Treeview",
            background=[("selected", "#24533A")],
            foreground=[("selected", "#FFFFFF")],
        )

    def _button(self, parent, text, command, width=90, primary=False, danger=False):
        if danger:
            fg = self.palette.red
            hover = "#DC2626"
            text_color = "#FFFFFF"
        elif primary:
            fg = self.palette.accent
            hover = "#16A34A"
            text_color = "#07110A"
        else:
            fg = self.palette.card_2
            hover = self.palette.hover
            text_color = self.palette.text
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=34,
            corner_radius=9,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            border_width=0 if (primary or danger) else 1,
            border_color=self.palette.border,
            font=("Segoe UI Semibold", 9),
            command=command,
        )

    def _build_header(self):
        header = ctk.CTkFrame(
            self.frame,
            height=72,
            fg_color=self.palette.card,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=14,
        )
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        logo = get_ctk_image(40)
        ctk.CTkLabel(
            header,
            text="",
            image=logo,
            width=50,
            height=50,
            fg_color="transparent",
        ).grid(row=0, column=0, padx=(12, 4), pady=10)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="ew", padx=7)
        ctk.CTkLabel(
            title_box,
            text="Otomasyon Merkezi",
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 21),
            anchor="w",
        ).pack(fill="x", pady=(7, 0))
        self.worker_label = ctk.CTkLabel(
            title_box,
            text=f"Sağlam görev motoru · v{AUTOMATION_BUILD}",
            text_color=self.palette.muted,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.worker_label.pack(fill="x", pady=(0, 5))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(5, 12), pady=10)
        self._button(actions, "+ Yeni", self.new_automation, 62, primary=True).pack(side="left", padx=2)
        self._button(actions, "Worker", self.toggle_worker, 58).pack(side="left", padx=2)
        self._button(actions, "Yenile", self.refresh_all, 58).pack(side="left", padx=2)
        if callable(self.close_command):
            self._button(actions, "‹ Geri", self.close_command, 55).pack(side="left", padx=(5, 0))

    def _build_body(self):
        pane = tk_paned(self.frame, self.palette)
        pane.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        left = ctk.CTkFrame(
            pane,
            width=330,
            fg_color=self.palette.card,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=12,
        )
        right = ctk.CTkFrame(
            pane,
            fg_color=self.palette.card,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=12,
        )
        try:
            narrow = int(self.root.winfo_width()) < 900
        except Exception:
            narrow = False
        pane.add(left, minsize=190 if narrow else 270, width=220 if narrow else 330, stretch="never")
        pane.add(right, minsize=230 if narrow else 520, stretch="always")

        navigation = ctk.CTkFrame(left, fg_color="transparent")
        navigation.pack(fill="x", padx=10, pady=(10, 4))
        self._button(navigation, "Otomasyonlar", self.refresh_list, 138, primary=True).pack(fill="x", pady=2)
        self._button(navigation, "Çalışmalar", lambda: self.tabs.set("Çalışmalar"), 138).pack(fill="x", pady=2)
        self._button(navigation, "Loglar", lambda: self.tabs.set("Log"), 138).pack(fill="x", pady=2)

        ctk.CTkLabel(
            left,
            text="YEREL GÖREVLER",
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).pack(fill="x", padx=13, pady=(12, 7))

        self.search_entry = ctk.CTkEntry(
            left,
            placeholder_text="Otomasyon ara…",
            height=33,
            fg_color=self.palette.card_2,
            border_color=self.palette.border,
            text_color=self.palette.text,
        )
        self.search_entry.pack(fill="x", padx=11, pady=(0, 7))
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_list())

        self.list_frame = ctk.CTkScrollableFrame(
            left,
            fg_color=self.palette.card_2,
            corner_radius=10,
            border_width=0,
        )
        self.list_frame.pack(fill="both", expand=True, padx=9, pady=(0, 9))

        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        detail_header = ctk.CTkFrame(right, fg_color="transparent")
        detail_header.grid(row=0, column=0, sticky="ew", padx=13, pady=(11, 4))
        detail_header.grid_columnconfigure(0, weight=1)

        self.detail_title = ctk.CTkLabel(
            detail_header,
            text="Bir otomasyon seç",
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 18),
            anchor="w",
        )
        self.detail_title.grid(row=0, column=0, sticky="ew")
        self.detail_status = ctk.CTkLabel(
            detail_header,
            text="",
            text_color=self.palette.muted,
            font=("Segoe UI", 9),
            anchor="e",
        )
        self.detail_status.grid(row=0, column=1, padx=(8, 0))

        self.tabs = ctk.CTkTabview(
            right,
            fg_color=self.palette.card,
            segmented_button_fg_color=self.palette.card_2,
            segmented_button_selected_color=self.palette.accent,
            segmented_button_selected_hover_color="#16A34A",
            segmented_button_unselected_color=self.palette.card_2,
            segmented_button_unselected_hover_color=self.palette.hover,
            text_color=self.palette.text,
            corner_radius=11,
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=9, pady=(3, 9))
        for title in ("Genel", "Çalışmalar", "Log"):
            self.tabs.add(title)

        self._build_general_tab()
        self._build_runs_tab()
        self._build_log_tab()

        # Video tasarımındaki alt kapsül çubuğu: seçili otomasyonun hızlı
        # işlemlerini tek, sabit ve hafif bir yüzeyde toplar.
        action_bar = ctk.CTkFrame(
            right,
            fg_color=self.palette.card_2,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=18,
            height=52,
        )
        action_bar.grid(row=2, column=0, sticky="ew", padx=13, pady=(0, 12))
        action_bar.grid_propagate(False)
        ctk.CTkLabel(
            action_bar,
            text="Seçili otomasyon için hızlı işlemler",
            text_color=self.palette.muted,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(14, 8))
        self._button(action_bar, "Yeni", self.new_automation, 58, primary=True).pack(side="right", padx=(3, 7), pady=8)
        self._button(action_bar, "Düzenle", self.edit_selected, 68).pack(side="right", padx=3, pady=8)
        self._button(action_bar, "Çalıştır", self.run_selected, 68).pack(side="right", padx=3, pady=8)
        self._button(action_bar, "Etkin/Pasif", self.toggle_selected_enabled, 82).pack(side="right", padx=3, pady=8)

    def _build_general_tab(self):
        tab = self.tabs.tab("Genel")
        self.general_text = ctk.CTkTextbox(
            tab,
            fg_color=self.palette.card_2,
            border_width=1,
            border_color=self.palette.border,
            text_color=self.palette.text,
            font=("Consolas", 10),
            wrap="word",
        )
        self.general_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.general_text.configure(state="disabled")

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.pack(fill="x", padx=4, pady=(0, 4))
        self._button(bottom, "Etkin/Pasif", self.toggle_selected_enabled, 96).pack(side="left", padx=2)
        self._button(bottom, "Önizle", self.preview_selected, 72).pack(side="left", padx=2)
        self._button(bottom, "Sağlık", self.health_selected, 64).pack(side="left", padx=2)
        self._button(bottom, "Deneme", self.dry_run_selected, 64).pack(side="left", padx=2)
        self._button(bottom, "Sil", self.delete_selected, 58, danger=True).pack(side="right", padx=2)
        safety = ctk.CTkFrame(tab, fg_color="transparent")
        safety.pack(fill="x", padx=4, pady=(0, 4))
        self._button(safety, "Geçmiş", self.show_history, 62).pack(side="left", padx=2)
        self._button(safety, "Taslağı aç", self.open_chat_draft, 72).pack(side="left", padx=2)
        self._button(safety, "Dışa aktar", self.export_data, 76).pack(side="left", padx=2)
        self._button(safety, "İçe aktar", self.import_data, 72).pack(side="left", padx=2)
        self.emergency_button = self._button(
            safety, "Acil durdur", self.toggle_emergency_stop, 85, danger=True
        )
        self.emergency_button.pack(side="left", padx=2)

    def _build_runs_tab(self):
        tab = self.tabs.tab("Çalışmalar")
        self.runs_tree = ttk.Treeview(
            tab,
            columns=("status", "started", "duration"),
            show="headings",
            style="Automation.Treeview",
            selectmode="browse",
        )
        for key, title, width in (
            ("status", "Durum", 90),
            ("started", "Başlangıç", 150),
            ("duration", "Süre", 80),
        ):
            self.runs_tree.heading(key, text=title)
            self.runs_tree.column(key, width=width, stretch=key == "started")
        self.runs_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.runs_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_selected_run_log())
        self.run_map: dict[str, dict[str, Any]] = {}
        self._button(
            tab, "Seçili çalışmayı geri al", self.rollback_selected_run, 170
        ).pack(anchor="w", padx=4, pady=(0, 4))

    def _build_log_tab(self):
        tab = self.tabs.tab("Log")
        self.log_text = ctk.CTkTextbox(
            tab,
            fg_color=self.palette.card_2,
            border_width=1,
            border_color=self.palette.border,
            text_color=self.palette.text,
            font=("Consolas", 10),
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text.configure(state="disabled")

    def refresh_all(self):
        self.refresh_list()
        self.refresh_details()
        self.refresh_worker_label()
        if hasattr(self, "emergency_button"):
            self.emergency_button.configure(
                text="Acil aç" if emergency_status().get("active") else "Acil durdur"
            )

    def refresh_list(self):
        query = self.search_entry.get().strip().casefold() if hasattr(self, "search_entry") else ""
        automations = list_automations()
        self.cards.clear()
        for child in self.list_frame.winfo_children():
            child.destroy()

        visible = [item for item in automations if not query or query in item.name.casefold() or query in TRIGGER_LABELS.get(item.trigger_type, item.trigger_type).casefold()]
        if not visible:
            ctk.CTkLabel(
                self.list_frame,
                text="Henüz otomasyon yok.",
                text_color=self.palette.muted,
                font=("Segoe UI", 10),
            ).pack(pady=24)
            return

        for automation in visible:
            selected = automation.id == self.selected_id
            card = ctk.CTkFrame(
                self.list_frame,
                fg_color="#1F3A2A" if selected else self.palette.card,
                border_width=1,
                border_color=self.palette.accent if selected else self.palette.border,
                corner_radius=10,
                cursor="hand2",
            )
            card.pack(fill="x", padx=3, pady=3)
            card.grid_columnconfigure(0, weight=1)

            name = ctk.CTkLabel(
                card,
                text=automation.name,
                text_color=self.palette.text,
                font=("Segoe UI Semibold", 11),
                anchor="w",
            )
            name.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 1))
            status = ctk.CTkLabel(
                card,
                text="Etkin" if automation.enabled else "Pasif",
                text_color=self.palette.accent if automation.enabled else self.palette.muted,
                font=("Segoe UI Semibold", 8),
            )
            status.grid(row=0, column=1, padx=8, pady=(8, 1))
            summary = ctk.CTkLabel(
                card,
                text=trigger_summary(automation.trigger_type, automation.trigger),
                text_color=self.palette.muted,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=255,
            )
            summary.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

            for widget in (card, name, status, summary):
                widget.bind("<Button-1>", lambda _e, aid=automation.id: self.select_automation(aid))
                widget.bind("<Enter>", lambda _e, item=card, aid=automation.id: self._card_hover(item, aid, True))
                widget.bind("<Leave>", lambda _e, item=card, aid=automation.id: self._card_hover(item, aid, False))
            self.cards[automation.id] = card

    def _card_hover(self, card, automation_id: str, active: bool):
        """Apply a lightweight hover state without blocking the Tk event loop."""
        try:
            if not card.winfo_exists() or automation_id == self.selected_id:
                return
            card.configure(fg_color=self.palette.hover if active else self.palette.card)
        except Exception:
            pass

    def select_automation(self, automation_id: str):
        self.selected_id = automation_id
        self.refresh_list()
        self.refresh_details()

    def refresh_details(self):
        if not self.selected_id:
            self.detail_title.configure(text="Bir otomasyon seç")
            self.detail_status.configure(text="")
            self._set_text(self.general_text, "")
            self._set_text(self.log_text, "")
            self.runs_tree.delete(*self.runs_tree.get_children())
            return
        try:
            automation = get_automation(self.selected_id)
        except Exception:
            self.selected_id = None
            self.refresh_all()
            return

        self.detail_title.configure(text=automation.name)
        self.detail_status.configure(
            text="ETKİN" if automation.enabled else "PASİF",
            text_color=self.palette.accent if automation.enabled else self.palette.muted,
        )
        permissions = get_required_permissions(automation.actions)
        lines = [
            f"Tetikleyici : {TRIGGER_LABELS.get(automation.trigger_type, automation.trigger_type)}",
            f"Ayrıntı     : {trigger_summary(automation.trigger_type, automation.trigger)}",
            f"Son çalışma : {format_ts(automation.last_run_at)}",
            f"Sonraki     : {format_ts(automation.next_run_at)}",
            f"İzinler     : {', '.join(PERMISSION_LABELS.get(item, item) for item in permissions) or 'Yok'}",
            f"Rollback    : {'Açık' if automation.policy.get('rollback_on_failure', True) else 'Kapalı'}",
            f"Tekrar      : {automation.policy.get('max_retries', 1)}",
            "",
            "İŞLEMLER",
        ]
        for index, action in enumerate(automation.actions, 1):
            lines.append(f"{index:02d}. {action_summary(action)}")
        self._set_text(self.general_text, "\n".join(lines))
        self.refresh_runs()

    def refresh_runs(self):
        self.runs_tree.delete(*self.runs_tree.get_children())
        self.run_map.clear()
        if not self.selected_id:
            return
        for run in list_runs(self.selected_id, 100):
            started = float(run["started_at"] or 0)
            finished = float(run["finished_at"] or 0)
            duration = f"{finished - started:.1f}s" if finished else "Çalışıyor"
            item = self.runs_tree.insert(
                "",
                "end",
                values=(run["status"], format_ts(started), duration),
            )
            self.run_map[item] = run

    def show_selected_run_log(self):
        selected = self.runs_tree.selection()
        if not selected:
            return
        run = self.run_map.get(selected[0])
        if not run:
            return
        events = list_events(run["id"], 1000)
        lines = [
            f"Run: {run['id']}",
            f"Durum: {run['status']}",
            f"Başlangıç: {format_ts(run['started_at'])}",
            f"Bitiş: {format_ts(run['finished_at'])}",
            "",
        ]
        for event in events:
            stamp = dt.datetime.fromtimestamp(event["ts"]).strftime("%H:%M:%S")
            lines.append(f"[{stamp}] {event['level']}: {event['message']}")
            if event.get("data"):
                data = json.dumps(event["data"], ensure_ascii=False, indent=2)
                lines.append(data)
        if run.get("error"):
            lines.extend(["", "HATA", str(run["error"])])
        self._set_text(self.log_text, "\n".join(lines))
        self.tabs.set("Log")

    def _set_text(self, textbox, value: str):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", value)
        textbox.configure(state="disabled")

    def refresh_worker_label(self):
        if emergency_status().get("active"):
            self.worker_label.configure(text="ACİL DURDURMA AKTİF · Yeni görevler bekletiliyor", text_color=self.palette.red)
            self.last_worker_alive = False
            return
        status = worker_status()
        alive = bool(status.get("alive"))
        profile_text = status.get("profile") or ""
        if alive:
            text = f"Worker çalışıyor · PID {status.get('pid')} · profil {profile_text}"
            color = self.palette.accent
        elif profile_allows_scheduler():
            text = "Worker kapalı · Dengeli/Tam profilde zamanlanmış görevler için başlatılabilir"
            color = self.palette.yellow
        else:
            text = "Hızlı profil · yalnızca manuel çalıştırma"
            color = self.palette.muted
        self.worker_label.configure(text=text, text_color=color)
        self.last_worker_alive = alive

    def _refresh_loop(self):
        if self.closed:
            return
        self.refresh_worker_label()
        if self.selected_id:
            self.refresh_runs()
        self.refresh_job = self.frame.after(2500, self._refresh_loop)

    def _open_editor(self, automation: Optional[AutomationDefinition] = None):
        current = self._active_editor
        try:
            if current is not None and current.window.winfo_exists():
                current.present()
                return current
        except Exception:
            self._active_editor = None
        editor = AutomationEditor(self, automation)
        self._active_editor = editor
        self._editors.append(editor)
        editor.present()
        return editor

    def new_automation(self):
        self._open_editor()

    def open_draft(self, draft: dict[str, Any]):
        if not isinstance(draft, dict):
            raise ValidationError("Otomasyon taslağı geçersiz.")
        editor = AutomationEditor(self, None, draft=draft)
        self._editors.append(editor)
        self._active_editor = editor
        editor.present()
        return editor

    def edit_selected(self):
        if not self.selected_id:
            return
        self._open_editor(get_automation(self.selected_id))

    def run_selected(self):
        if not self.selected_id:
            return
        try:
            process = run_in_subprocess(self.selected_id, {"type": "manual", "source": "ui"})
            self.detail_status.configure(text=f"KUYRUKTA · PID {process.pid}", text_color=self.palette.blue)
            self.frame.after(800, self.refresh_details)
        except Exception as exc:
            messagebox.showerror("Otomasyon", str(exc), parent=self.root)

    def health_selected(self):
        if not self.selected_id:
            return
        try:
            report = health_check(self.selected_id)
        except Exception as exc:
            messagebox.showerror("Sağlık kontrolü", str(exc), parent=self.root)
            return
        lines = [
            f"Otomasyon: {report['name']}",
            f"Sonuç: {'HAZIR' if report['ok'] else 'SORUN VAR'}",
            f"Risk: {report['risk']}",
            "",
            "Kontroller:",
        ]
        lines.extend(
            f"{'OK' if item['ok'] else 'HATA'} · {item['name']}: {item['message']}"
            for item in report["checks"]
        )
        if report["warnings"]:
            lines.extend(["", "Uyarılar:", *report["warnings"]])
        if report["errors"]:
            lines.extend(["", "Hatalar:", *report["errors"]])
        messagebox.showinfo("Otomasyon sağlık kontrolü", "\n".join(lines), parent=self.root)

    def dry_run_selected(self):
        if not self.selected_id:
            return
        automation_id = self.selected_id
        self.detail_status.configure(text="DENEME HAZIRLANIYOR…", text_color=self.palette.yellow)

        def worker():
            try:
                result = dry_run(automation_id)
                error = None
            except Exception as exc:
                result = None
                error = str(exc)

            def show():
                if error:
                    messagebox.showerror("Deneme çalışması", error, parent=self.root)
                    return
                preview = (result or {}).get("preview") or {}
                lines = [
                    "Deneme tamamlandı. Gerçek işlem uygulanmadı.",
                    "",
                    f"Otomasyon: {preview.get('name', '')}",
                    f"İşlem sayısı: {len(preview.get('actions') or [])}",
                ]
                if preview.get("warnings"):
                    lines.extend(["", "Uyarılar:", *[str(item) for item in preview["warnings"]]])
                messagebox.showinfo("Deneme çalışması", "\n".join(lines), parent=self.root)
                self.refresh_details()

            try:
                self.frame.after(0, show)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="NetoAutomationDryRun").start()

    def rollback_selected_run(self):
        selected = self.runs_tree.selection()
        run = self.run_map.get(selected[0]) if selected else None
        if not run:
            messagebox.showinfo("Geri al", "Önce bir çalışma seç.", parent=self.root)
            return
        if not messagebox.askyesno(
            "Çalışmayı geri al",
            "Bu çalışmadaki geri alınabilir dosya işlemleri geri alınsın mı?",
            parent=self.root,
        ):
            return
        try:
            result = rollback_run(run["id"])
            messagebox.showinfo(
                "Geri alındı",
                f"{result['rolled_back']} işlem geri alındı."
                + (f"\nHata: {', '.join(result['errors'])}" if result["errors"] else ""),
                parent=self.root,
            )
            self.refresh_details()
        except Exception as exc:
            messagebox.showerror("Geri alınamadı", str(exc), parent=self.root)

    def show_history(self):
        items = history(120)
        if not items:
            messagebox.showinfo("Geçmiş", "Henüz işlem geçmişi yok.", parent=self.root)
            return
        lines = ["NetOps işlem geçmişi", ""]
        for item in items:
            stamp = format_ts(float(item.get("ts") or 0))
            lines.append(
                f"{stamp} · {item['kind']} · {item['status']} · {item['automation_id']}"
            )
            if item.get("error"):
                lines.append(f"  Hata: {item['error']}")
        messagebox.showinfo("Geçmiş", "\n".join(lines), parent=self.root)

    def open_chat_draft(self):
        try:
            import neto_ai

            draft = neto_ai.son_automation_draft()
        except Exception:
            draft = None
        if not draft:
            messagebox.showinfo(
                "Otomasyon taslağı",
                "Sohbette onay bekleyen bir otomasyon taslağı yok.",
                parent=self.root,
            )
            return
        self.open_draft(draft)

    def toggle_emergency_stop(self):
        state = emergency_status()
        if state.get("active"):
            clear_emergency_stop()
            self.emergency_button.configure(text="Acil durdur")
            if profile_allows_scheduler():
                threading.Thread(target=start_worker, daemon=True, name="NetoAutomationWorkerResume").start()
            self.refresh_worker_label()
            return
        result = emergency_stop_all()
        self.emergency_button.configure(text="Acil aç")
        self.detail_status.configure(text="ACİL DURDURMA AKTİF", text_color=self.palette.red)
        messagebox.showwarning(
            "Acil durdurma",
            f"Yeni otomasyonlar durduruldu. Sonlandırılan süreç: {len(result.get('terminated_pids', []))}.",
            parent=self.root,
        )

    def export_data(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="NetOps yedeğini kaydet",
            defaultextension=".json",
            filetypes=[("NetOps yedeği", "*.json"), ("Tüm dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            result = export_bundle(path)
            messagebox.showinfo(
                "Yedek oluşturuldu",
                f"{result['automations']} otomasyon ve {result['scenes']} sahne dışa aktarıldı.",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Yedek oluşturulamadı", str(exc), parent=self.root)

    def import_data(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="NetOps yedeğini seç",
            filetypes=[("NetOps yedeği", "*.json"), ("Tüm dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            result = import_bundle(path)
            messagebox.showinfo(
                "Yedek içe aktarıldı",
                f"{result['automations']} otomasyon ve {result['scenes']} sahne eklendi."
                "\nHiçbir işlem otomatik çalıştırılmadı.",
                parent=self.root,
            )
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Yedek içe aktarılamadı", str(exc), parent=self.root)

    def toggle_selected_enabled(self):
        if not self.selected_id:
            return
        automation = get_automation(self.selected_id)
        set_enabled(automation.id, not automation.enabled)
        self.refresh_all()

    def delete_selected(self):
        if not self.selected_id:
            return
        automation = get_automation(self.selected_id)
        if not messagebox.askyesno(
            "Otomasyonu sil",
            f"{automation.name} kalıcı olarak silinsin mi?\n\nÇalışma logları da silinir.",
            parent=self.root,
            icon="warning",
        ):
            return
        delete_automation(automation.id)
        self.selected_id = None
        self.refresh_all()

    def preview_selected(self):
        if not self.selected_id:
            return
        automation = get_automation(self.selected_id)
        preview = preview_automation(
            name=automation.name,
            trigger_type=automation.trigger_type,
            trigger=automation.trigger,
            actions=automation.actions,
            policy=automation.policy,
        )
        permissions = [
            str(PERMISSION_LABELS.get(item, item or ""))
            for item in (preview.get("permissions") or [])
            if item is not None
        ]
        lines = [
            f"Otomasyon: {automation.name}",
            f"Tetikleyici: {trigger_summary(automation.trigger_type, automation.trigger)}",
            "İzinler: " + ", ".join(permissions),
            "",
            "İşlem planı:",
        ]
        lines.extend(f"{index}. {action_summary(action)}" for index, action in enumerate(preview["actions"], 1))
        if preview["warnings"]:
            lines.extend(["", "Uyarılar:", *preview["warnings"]])
        messagebox.showinfo("Otomasyon önizleme", "\n".join(lines), parent=self.root)

    def toggle_worker(self):
        status = worker_status()
        if status.get("alive"):
            ok = stop_worker()
            if not ok:
                messagebox.showerror("Worker", "Worker durdurulamadı.", parent=self.root)
        else:
            result = start_worker(force=True)
            if not result.get("alive") and not result.get("starting"):
                messagebox.showerror("Worker", f"Worker başlatılamadı: {result}", parent=self.root)
        self.frame.after(700, self.refresh_worker_label)

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        if self.refresh_job is not None:
            try:
                self.frame.after_cancel(self.refresh_job)
            except Exception:
                pass


class AutomationEditor:
    def __init__(
        self,
        panel: AutomationPanel,
        automation: Optional[AutomationDefinition],
        draft: Optional[dict[str, Any]] = None,
    ):
        self.panel = panel
        self.automation = automation
        self.draft = draft
        self.palette = panel.palette
        if automation:
            self.actions = [dict(item) for item in automation.actions]
        else:
            self.actions = [dict(item) for item in (draft or {}).get("actions", [])]
        self.action_widgets: list[Any] = []
        self._action_editors: list[Any] = []

        self.window = ctk.CTkToplevel(panel.root)
        self.window.title("Otomasyon düzenle" if automation else "Yeni otomasyon")
        self.window.geometry("840x760")
        self.window.minsize(760, 650)
        self.window.configure(fg_color=self.palette.bg)
        apply_window_icon(self.window)
        try:
            self.window.transient(panel.root)
        except Exception:
            pass

        self.shell = ctk.CTkScrollableFrame(
            self.window,
            fg_color=self.palette.card,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=16,
        )
        self.shell.pack(fill="both", expand=True, padx=14, pady=14)

        self._build_identity()
        self._build_trigger()
        self._build_actions()
        self._build_policy()
        self._build_footer()
        if self.draft:
            self._load_draft()
        else:
            self._load_existing()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def present(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        try:
            self.window.grab_set()
        except Exception:
            pass

    def _label(self, text):
        return ctk.CTkLabel(
            self.shell,
            text=text,
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        )

    def _entry(self, parent, placeholder=""):
        return ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            height=34,
            fg_color=self.palette.card_2,
            border_color=self.palette.border,
            text_color=self.palette.text,
        )

    def _section(self, title: str):
        frame = ctk.CTkFrame(
            self.shell,
            fg_color=self.palette.card_2,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=12,
        )
        frame.pack(fill="x", padx=5, pady=6)
        ctk.CTkLabel(
            frame,
            text=title,
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 5))
        return frame

    def _build_identity(self):
        section = self._section("Temel bilgiler")
        self.name_entry = self._entry(section, "Örn. Gece Pixarea yedeği")
        self.name_entry.pack(fill="x", padx=12, pady=(0, 10))
        self.enabled_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            section,
            text="Otomasyon etkin",
            variable=self.enabled_var,
            text_color=self.palette.text,
            fg_color=self.palette.accent,
            hover_color=self.palette.hover,
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _build_trigger(self):
        section = self._section("Tetikleyici")
        reverse = {label: key for key, label in TRIGGER_LABELS.items()}
        self.trigger_reverse = reverse
        self.trigger_var = ctk.StringVar(value=TRIGGER_LABELS["manual"])
        self.trigger_menu = ctk.CTkOptionMenu(
            section,
            variable=self.trigger_var,
            values=list(reverse),
            height=34,
            fg_color=self.palette.card,
            button_color=self.palette.card,
            button_hover_color=self.palette.hover,
            text_color=self.palette.text,
            command=lambda _value: self.render_trigger_fields(),
        )
        self.trigger_menu.pack(fill="x", padx=12, pady=(0, 8))
        self.trigger_fields = ctk.CTkFrame(section, fg_color="transparent")
        self.trigger_fields.pack(fill="x", padx=12, pady=(0, 10))
        self.trigger_inputs: dict[str, Any] = {}
        self.render_trigger_fields()

    def _input_row(self, parent, label, key, default: Any = ""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            row,
            text=label,
            width=170,
            text_color=self.palette.muted,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left")
        entry = self._entry(row)
        entry.pack(side="left", fill="x", expand=True)
        if default not in (None, ""):
            entry.insert(0, str(default))
        self.trigger_inputs[key] = entry
        return entry

    def _path_row(self, parent, label, key, directory=False):
        entry = self._input_row(parent, label, key)
        def choose():
            path = filedialog.askdirectory(parent=self.window) if directory else filedialog.askopenfilename(parent=self.window)
            if path:
                entry.delete(0, "end")
                entry.insert(0, path)
        ctk.CTkButton(
            entry.master,
            text="Seç",
            width=54,
            height=32,
            fg_color=self.palette.card,
            hover_color=self.palette.hover,
            text_color=self.palette.text,
            command=choose,
        ).pack(side="left", padx=(5, 0))
        return entry

    def render_trigger_fields(self):
        for child in self.trigger_fields.winfo_children():
            child.destroy()
        self.trigger_inputs.clear()
        trigger_type = self.trigger_reverse.get(self.trigger_var.get(), "manual")

        if trigger_type == "manual":
            ctk.CTkLabel(
                self.trigger_fields,
                text="Bu otomasyon yalnızca Çalıştır düğmesiyle başlar.",
                text_color=self.palette.muted,
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x")
        elif trigger_type == "interval":
            self._input_row(self.trigger_fields, "Aralık (saniye)", "seconds", 300)
        elif trigger_type == "daily":
            self._input_row(self.trigger_fields, "Saat (HH:MM)", "time", "23:00")
            self._input_row(self.trigger_fields, "Günler (0=Pzt…6=Paz)", "weekdays", "0,1,2,3,4,5,6")
        elif trigger_type == "startup":
            self._input_row(self.trigger_fields, "Gecikme (saniye)", "delay_seconds", 5)
        elif trigger_type == "file_change":
            self._path_row(self.trigger_fields, "Dosya / klasör", "path", directory=True)
            self._input_row(self.trigger_fields, "Bekleme / debounce", "debounce_seconds", 3)
            self._input_row(self.trigger_fields, "Alt klasörler (1/0)", "recursive", 1)
        elif trigger_type == "internet_online":
            self._input_row(self.trigger_fields, "Sunucu", "host", "1.1.1.1")
            self._input_row(self.trigger_fields, "Port", "port", 53)
            self._input_row(self.trigger_fields, "Zaman aşımı", "timeout_seconds", 3)
        elif trigger_type == "resource_threshold":
            self._input_row(self.trigger_fields, "Metrik (cpu/memory/disk)", "metric", "cpu")
            self._input_row(self.trigger_fields, "Operatör", "operator", ">=")
            self._input_row(self.trigger_fields, "Eşik (%)", "threshold", 85)
            self._input_row(self.trigger_fields, "Sürdürme (sn)", "sustain_seconds", 10)
            self._input_row(self.trigger_fields, "Bekleme (sn)", "cooldown_seconds", 300)
            self._input_row(self.trigger_fields, "Disk yolu", "path", "C:\\")
        elif trigger_type == "process_open":
            self._input_row(self.trigger_fields, "Program adı", "process_name", "notepad.exe")
            self._input_row(self.trigger_fields, "Bekleme (sn)", "cooldown_seconds", 300)

    def _build_actions(self):
        section = self._section("İşlemler")
        toolbar = ctk.CTkFrame(section, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(0, 6))
        self.panel._button(toolbar, "+ İşlem ekle", self.add_action, 100, primary=True).pack(side="left")
        ctk.CTkLabel(
            toolbar,
            text="İşlemler sırayla çalışır. Hata olursa desteklenen dosya işlemleri geri alınır.",
            text_color=self.palette.muted,
            font=("Segoe UI", 8),
            anchor="e",
        ).pack(side="right")
        self.actions_frame = ctk.CTkFrame(section, fg_color="transparent")
        self.actions_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.render_actions()

    def render_actions(self):
        for child in self.actions_frame.winfo_children():
            child.destroy()
        if not self.actions:
            ctk.CTkLabel(
                self.actions_frame,
                text="Henüz işlem eklenmedi.",
                text_color=self.palette.muted,
                font=("Segoe UI", 9),
            ).pack(pady=12)
            return
        for index, action in enumerate(self.actions):
            row = ctk.CTkFrame(
                self.actions_frame,
                fg_color=self.palette.card,
                border_width=1,
                border_color=self.palette.border,
                corner_radius=9,
            )
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row,
                text=f"{index + 1}. {action_summary(action)}",
                text_color=self.palette.text,
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=580,
            ).grid(row=0, column=0, sticky="ew", padx=9, pady=8)
            self.panel._button(row, "Düzenle", lambda i=index: self.edit_action(i), 60).grid(row=0, column=1, padx=2)
            self.panel._button(row, "↑", lambda i=index: self.move_action(i, -1), 34).grid(row=0, column=2, padx=1)
            self.panel._button(row, "↓", lambda i=index: self.move_action(i, 1), 34).grid(row=0, column=3, padx=1)
            self.panel._button(row, "Sil", lambda i=index: self.remove_action(i), 44, danger=True).grid(row=0, column=4, padx=(2, 7))

    def add_action(self):
        action_editor = ActionEditor(self, None, None)
        self._action_editors.append(action_editor)
        action_editor.present()

    def edit_action(self, index: int):
        action_editor = ActionEditor(self, index, self.actions[index])
        self._action_editors.append(action_editor)
        action_editor.present()

    def set_action(self, index: Optional[int], action: dict[str, Any]):
        if index is None:
            self.actions.append(action)
        else:
            self.actions[index] = action
        self.render_actions()

    def remove_action(self, index: int):
        self.actions.pop(index)
        self.render_actions()

    def move_action(self, index: int, direction: int):
        target = index + direction
        if target < 0 or target >= len(self.actions):
            return
        self.actions[index], self.actions[target] = self.actions[target], self.actions[index]
        self.render_actions()

    def _build_policy(self):
        section = self._section("Güvenlik ve hata politikası")
        self.rollback_var = ctk.BooleanVar(value=True)
        self.dangerous_var = ctk.BooleanVar(value=False)
        self.continue_var = ctk.BooleanVar(value=False)
        for text, variable in (
            ("Hata halinde geri alınabilen dosya işlemlerini geri al", self.rollback_var),
            ("Tehlikeli komutlara açıkça izin ver", self.dangerous_var),
            ("Bir işlem hata verirse sonraki işleme devam et", self.continue_var),
        ):
            ctk.CTkCheckBox(
                section,
                text=text,
                variable=variable,
                text_color=self.palette.text,
                fg_color=self.palette.accent,
            hover_color=self.palette.hover,
            ).pack(anchor="w", padx=12, pady=3)

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(6, 10))
        self.retry_entry = self._entry(row)
        self.retry_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.retry_entry.insert(0, "1")
        self.retry_entry.configure(placeholder_text="Maksimum tekrar")
        self.cooldown_entry = self._entry(row)
        self.cooldown_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.cooldown_entry.insert(0, "0")
        self.cooldown_entry.configure(placeholder_text="Çalışmalar arası bekleme")

    def _build_footer(self):
        footer = ctk.CTkFrame(self.shell, fg_color="transparent")
        footer.pack(fill="x", padx=5, pady=(6, 12))
        self.panel._button(footer, "Önizle", self.preview, 80).pack(side="left")
        self.panel._button(footer, "İptal", self.close, 72).pack(side="right", padx=3)
        self.panel._button(footer, "Kaydet", self.save, 82, primary=True).pack(side="right", padx=3)

    def _load_existing(self):
        if not self.automation:
            return
        automation = self.automation
        self.name_entry.insert(0, automation.name)
        self.enabled_var.set(automation.enabled)
        self.trigger_var.set(TRIGGER_LABELS.get(automation.trigger_type, automation.trigger_type))
        self.render_trigger_fields()
        for key, entry in self.trigger_inputs.items():
            value = automation.trigger.get(key, "")
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            entry.delete(0, "end")
            entry.insert(0, str(int(value)) if isinstance(value, bool) else str(value))
        self.rollback_var.set(bool(automation.policy.get("rollback_on_failure", True)))
        self.dangerous_var.set(bool(automation.policy.get("allow_dangerous_commands", False)))
        self.continue_var.set(bool(automation.policy.get("continue_on_action_error", False)))
        self.retry_entry.delete(0, "end")
        self.retry_entry.insert(0, str(automation.policy.get("max_retries", 1)))
        self.cooldown_entry.delete(0, "end")
        self.cooldown_entry.insert(0, str(automation.policy.get("cooldown_seconds", 0)))

    def _load_draft(self):
        draft = self.draft or {}
        self.name_entry.insert(0, str(draft.get("name") or "Sohbet taslağı"))
        self.enabled_var.set(False)
        trigger_type = str(draft.get("trigger_type") or "manual")
        self.trigger_var.set(TRIGGER_LABELS.get(trigger_type, TRIGGER_LABELS["manual"]))
        self.render_trigger_fields()
        trigger = draft.get("trigger") if isinstance(draft.get("trigger"), dict) else {}
        for key, entry in self.trigger_inputs.items():
            value = trigger.get(key, "")
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            entry.delete(0, "end")
            entry.insert(0, str(value))

    def collect_trigger(self):
        trigger_type = self.trigger_reverse.get(self.trigger_var.get(), "manual")
        raw = {key: entry.get().strip() for key, entry in self.trigger_inputs.items()}
        if "weekdays" in raw:
            raw["weekdays"] = [int(item.strip()) for item in raw["weekdays"].split(",") if item.strip()]
        for key in ("seconds", "delay_seconds", "debounce_seconds", "port", "sustain_seconds", "cooldown_seconds"):
            if key in raw and raw[key] != "":
                raw[key] = int(float(raw[key]))
        for key in ("timeout_seconds", "threshold"):
            if key in raw and raw[key] != "":
                raw[key] = float(raw[key])
        if "recursive" in raw:
            raw["recursive"] = raw["recursive"].casefold() not in {"0", "false", "hayır", "hayir"}
        return trigger_type, raw

    def collect_policy(self):
        return {
            "max_retries": int(self.retry_entry.get() or 0),
            "retry_delay_seconds": 3,
            "rollback_on_failure": bool(self.rollback_var.get()),
            "allow_dangerous_commands": bool(self.dangerous_var.get()),
            "continue_on_action_error": bool(self.continue_var.get()),
            "cooldown_seconds": int(self.cooldown_entry.get() or 0),
            "timeout_seconds": 300,
        }

    def preview(self):
        try:
            trigger_type, trigger = self.collect_trigger()
            value = preview_automation(
                name=self.name_entry.get(),
                trigger_type=trigger_type,
                trigger=trigger,
                actions=self.actions,
                policy=self.collect_policy(),
            )
        except Exception as exc:
            messagebox.showerror("Otomasyon", str(exc), parent=self.window)
            return
        permissions = [
            str(PERMISSION_LABELS.get(item, item or ""))
            for item in (value.get("permissions") or [])
            if item is not None
        ]
        lines = [
            f"Tetikleyici: {trigger_summary(value['trigger_type'], value['trigger'])}",
            "İzinler: " + ", ".join(permissions),
            "",
        ]
        lines.extend(f"{index}. {action_summary(action)}" for index, action in enumerate(value["actions"], 1))
        if value["warnings"]:
            lines.extend(["", "Uyarılar:", *value["warnings"]])
        messagebox.showinfo("Otomasyon planı", "\n".join(lines), parent=self.window)

    def save(self):
        try:
            trigger_type, trigger = self.collect_trigger()
            kwargs = {
                "name": self.name_entry.get(),
                "trigger_type": trigger_type,
                "trigger": trigger,
                "actions": self.actions,
                "policy": self.collect_policy(),
                "enabled": bool(self.enabled_var.get()),
            }
            if self.automation:
                update_automation(self.automation.id, **kwargs)
                automation_id = self.automation.id
            else:
                automation_id = create_automation(**kwargs)
        except Exception as exc:
            messagebox.showerror("Otomasyon kaydedilemedi", str(exc), parent=self.window)
            return
        self.panel.selected_id = automation_id
        if profile_allows_scheduler():
            threading.Thread(target=start_worker, daemon=True, name="NetoAutomationWorkerStart").start()
        self.close()
        try:
            self.panel.frame.after_idle(self.panel.refresh_all)
        except Exception:
            pass

    def close(self):
        try:
            self.window.grab_release()
        except Exception:
            pass
        if getattr(self.panel, "_active_editor", None) is self:
            self.panel._active_editor = None
        try:
            self.panel._editors.remove(self)
        except (ValueError, AttributeError):
            pass
        self.window.destroy()


class ActionEditor:
    def __init__(self, editor: AutomationEditor, index: Optional[int], action: Optional[dict[str, Any]]):
        self.editor = editor
        self.index = index
        self.action = dict(action or {})
        self.palette = editor.palette
        self.inputs: dict[str, Any] = {}
        self.vars: dict[str, Any] = {}

        self.window = ctk.CTkToplevel(editor.window)
        self.window.title("İşlem düzenle" if action else "İşlem ekle")
        self.window.geometry("680x640")
        self.window.minsize(600, 520)
        self.window.configure(fg_color=self.palette.bg)
        apply_window_icon(self.window)
        try:
            self.window.transient(editor.window)
        except Exception:
            pass

        shell = ctk.CTkScrollableFrame(
            self.window,
            fg_color=self.palette.card,
            border_width=1,
            border_color=self.palette.border,
            corner_radius=15,
        )
        shell.pack(fill="both", expand=True, padx=13, pady=13)
        self.shell = shell

        ctk.CTkLabel(
            shell,
            text="İşlem türü",
            text_color=self.palette.text,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(10, 5))
        self.reverse = {label: key for key, label in ACTION_LABELS.items()}
        initial_type = self.action.get("type", "notify")
        self.type_var = ctk.StringVar(value=ACTION_LABELS.get(initial_type, ACTION_LABELS["notify"]))
        self.type_menu = ctk.CTkOptionMenu(
            shell,
            variable=self.type_var,
            values=list(self.reverse),
            height=35,
            fg_color=self.palette.card_2,
            button_color=self.palette.card_2,
            button_hover_color=self.palette.hover,
            text_color=self.palette.text,
            command=lambda _value: self.render_fields(),
        )
        self.type_menu.pack(fill="x", padx=10, pady=(0, 8))

        self.fields = ctk.CTkFrame(shell, fg_color="transparent")
        self.fields.pack(fill="x", padx=10, pady=4)
        self.render_fields()

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=(12, 10))
        editor.panel._button(footer, "İptal", self.close, 72).pack(side="right", padx=3)
        editor.panel._button(footer, "Kaydet", self.save, 82, primary=True).pack(side="right", padx=3)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def present(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        try:
            self.window.grab_set()
        except Exception:
            pass

    def _entry_row(self, label, key, default="", multiline=False, path_mode=None):
        ctk.CTkLabel(
            self.fields,
            text=label,
            text_color=self.palette.muted,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(5, 2))
        if multiline:
            widget = ctk.CTkTextbox(
                self.fields,
                height=90,
                fg_color=self.palette.card_2,
                border_width=1,
                border_color=self.palette.border,
                text_color=self.palette.text,
                font=("Consolas", 10),
            )
            widget.pack(fill="x")
            if default not in (None, ""):
                widget.insert("1.0", str(default))
        else:
            row = ctk.CTkFrame(self.fields, fg_color="transparent")
            row.pack(fill="x")
            widget = ctk.CTkEntry(
                row,
                height=34,
                fg_color=self.palette.card_2,
                border_color=self.palette.border,
                text_color=self.palette.text,
            )
            widget.pack(side="left", fill="x", expand=True)
            if default not in (None, ""):
                widget.insert(0, str(default))
            if path_mode:
                def choose():
                    if path_mode == "directory":
                        value = filedialog.askdirectory(parent=self.window)
                    elif path_mode == "save":
                        value = filedialog.asksaveasfilename(parent=self.window)
                    else:
                        value = filedialog.askopenfilename(parent=self.window)
                    if value:
                        widget.delete(0, "end")
                        widget.insert(0, value)
                ctk.CTkButton(
                    row,
                    text="Seç",
                    width=55,
                    height=32,
                    fg_color=self.palette.card_2,
                    hover_color=self.palette.hover,
                    text_color=self.palette.text,
                    command=choose,
                ).pack(side="left", padx=(5, 0))
        self.inputs[key] = widget
        return widget

    def _checkbox(self, text, key, default=False):
        variable = ctk.BooleanVar(value=bool(default))
        ctk.CTkCheckBox(
            self.fields,
            text=text,
            variable=variable,
            text_color=self.palette.text,
            fg_color=self.palette.accent,
            hover_color=self.palette.hover,
        ).pack(anchor="w", pady=5)
        self.vars[key] = variable

    def render_fields(self):
        for child in self.fields.winfo_children():
            child.destroy()
        self.inputs.clear()
        self.vars.clear()
        action_type = self.reverse.get(self.type_var.get(), "notify")
        value = self.action if self.action.get("type") == action_type else {}

        if action_type == "notify":
            self._entry_row("Başlık", "title", value.get("title", "Neto Otomasyon"))
            self._entry_row("Mesaj", "message", value.get("message", ""), multiline=True)
        elif action_type == "run_program":
            self._entry_row("Program yolu", "path", value.get("path", ""), path_mode="file")
            self._entry_row("Argümanlar (her satır bir argüman)", "args", "\n".join(value.get("args", [])), multiline=True)
            self._entry_row("Çalışma klasörü", "cwd", value.get("cwd", ""), path_mode="directory")
            self._checkbox("Program kapanana kadar bekle", "wait", value.get("wait", False))
        elif action_type == "run_command":
            self._entry_row("PowerShell / komut", "command", value.get("command", ""), multiline=True)
            self._entry_row("Çalışma klasörü", "cwd", value.get("cwd", ""), path_mode="directory")
            self._entry_row("Zaman aşımı (saniye)", "timeout_seconds", value.get("timeout_seconds", 120))
        elif action_type == "open_url":
            self._entry_row("URL", "url", value.get("url", "https://"))
        elif action_type in {"copy_file", "move_file"}:
            self._entry_row("Kaynak", "source", value.get("source", ""), path_mode="file")
            self._entry_row("Hedef", "destination", value.get("destination", ""), path_mode="save")
            self._checkbox("Hedef varsa üzerine yaz", "overwrite", value.get("overwrite", False))
        elif action_type == "backup_folder":
            self._entry_row("Kaynak klasör", "source", value.get("source", ""), path_mode="directory")
            self._entry_row("ZIP hedefi / klasörü", "destination", value.get("destination", ""), path_mode="save")
            self._checkbox("Dosya adına tarih ekle", "include_timestamp", value.get("include_timestamp", True))
        elif action_type == "http_request":
            self._entry_row("Yöntem", "method", value.get("method", "GET"))
            self._entry_row("URL", "url", value.get("url", "https://"))
            self._entry_row("Başlıklar (JSON)", "headers", json.dumps(value.get("headers", {}), ensure_ascii=False), multiline=True)
            body = value.get("body", "")
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, indent=2)
            self._entry_row("Gövde", "body", body, multiline=True)
            self._entry_row("Beklenen durum kodları", "expect_status", ",".join(str(item) for item in value.get("expect_status", [200, 201, 202, 204])))
        elif action_type == "public_api_watch":
            self._entry_row("API adı / kimliği", "api", value.get("api", ""))
            self._entry_row("Görünen ad", "api_label", value.get("api_label", ""))
            self._entry_row("Başlık", "title", value.get("title", "NetOps API Watch"))
            self._entry_row("Zaman aşımı (saniye)", "timeout_seconds", value.get("timeout_seconds", 8))
            notify_on = set(value.get("notify_on") or ["down", "recovered"])
            self._checkbox("Çökerse bildir", "notify_down", "down" in notify_on or "always" in notify_on)
            self._checkbox("Geri gelirse bildir", "notify_recovered", "recovered" in notify_on or "always" in notify_on)
            self._checkbox("Her kontrolde bildir", "notify_always", "always" in notify_on)
            self._checkbox("Çökük kaldığı sürece tekrar bildir", "repeat_down", value.get("repeat_down", False))
            ctk.CTkLabel(
                self.fields,
                text="Bu işlem verified Public-APIs kataloğundaki seçilen sağlayıcıyı fallback kullanmadan izler.",
                text_color=self.palette.muted,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))
        elif action_type == "wait":
            self._entry_row("Saniye", "seconds", value.get("seconds", 1))
        elif action_type == "shutdown":
            self._entry_row("Gecikme (saniye)", "delay_seconds", value.get("delay_seconds", 30))
            self._checkbox("Uygulamaları zorla kapat", "force", value.get("force", False))
            ctk.CTkLabel(
                self.fields,
                text="Bu işlem bilgisayarı kapatır. Güvenlik politikasında tehlikeli işlemlere izin verilmelidir.",
                text_color="#F59E0B",
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))
        elif action_type == "lua_script":
            self._entry_row("Lua scripti", "script", value.get("script", ""), multiline=True)
        elif action_type == "write_text":
            self._entry_row("Dosya yolu", "path", value.get("path", ""), path_mode="save")
            self._entry_row("Metin", "text", value.get("text", ""), multiline=True)
            self._checkbox("Dosyanın sonuna ekle", "append", value.get("append", False))
        elif action_type == "run_scene":
            self._entry_row("Sahne kimliği", "scene_id", value.get("scene_id", "work"))
            ctk.CTkLabel(
                self.fields,
                text="Sahne kimliğini Neto Hazırla panelindeki karttan kullanabilirsin.",
                text_color=self.palette.muted,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))
        condition = value.get("condition")
        condition_text = json.dumps(condition, ensure_ascii=False) if condition else ""
        self._entry_row(
            "Koşul (isteğe bağlı JSON)",
            "condition",
            condition_text,
            multiline=True,
        )

    def _get(self, key):
        widget = self.inputs.get(key)
        if widget is None:
            return None
        if isinstance(widget, ctk.CTkTextbox):
            return widget.get("1.0", "end-1c")
        return widget.get().strip()

    def save(self):
        action_type = self.reverse.get(self.type_var.get(), "notify")
        action: dict[str, Any] = {"type": action_type, "enabled": True}
        for key in self.inputs:
            action[key] = self._get(key)
        for key, variable in self.vars.items():
            action[key] = bool(variable.get())

        if action_type == "run_program":
            action["args"] = [line for line in str(action.get("args", "")).splitlines() if line.strip()]
        if action_type == "run_command":
            action["timeout_seconds"] = int(action.get("timeout_seconds") or 120)
        if action_type == "http_request":
            try:
                action["headers"] = json.loads(action.get("headers") or "{}")
            except Exception as exc:
                messagebox.showerror("İşlem", f"Başlık JSON'u geçersiz: {exc}", parent=self.window)
                return
            action["expect_status"] = [int(item.strip()) for item in str(action.get("expect_status", "200")).split(",") if item.strip()]
        if action_type == "public_api_watch":
            action["timeout_seconds"] = int(action.get("timeout_seconds") or 8)
            if action.pop("notify_always", False):
                action["notify_on"] = ["always"]
            else:
                notify_on = []
                if action.pop("notify_down", False):
                    notify_on.append("down")
                if action.pop("notify_recovered", False):
                    notify_on.append("recovered")
                action["notify_on"] = notify_on or ["down", "recovered"]
        if action_type == "wait":
            action["seconds"] = float(action.get("seconds") or 0)
        if action_type == "shutdown":
            action["delay_seconds"] = int(action.get("delay_seconds") or 30)
        condition_text = str(action.get("condition") or "").strip()
        if condition_text:
            try:
                action["condition"] = json.loads(condition_text)
            except Exception as exc:
                messagebox.showerror(
                    "İşlem koşulu",
                    f"Koşul JSON'u geçersiz: {exc}",
                    parent=self.window,
                )
                return
        else:
            action.pop("condition", None)

        self.editor.set_action(self.index, action)
        self.close()

    def close(self):
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.editor._action_editors.remove(self)
        except (ValueError, AttributeError):
            pass
        self.window.destroy()


def tk_paned(parent, palette: Palette):
    import tkinter as tk
    return tk.PanedWindow(
        parent,
        orient="horizontal",
        bg=palette.bg,
        bd=0,
        sashwidth=6,
        sashrelief="flat",
        showhandle=False,
    )


def create_automation_panel(
    parent,
    *,
    root=None,
    palette_getter=None,
    close_command=None,
):
    if not profile_allows_panel():
        raise AutomationError("Otomasyon Merkezi Zorla Hızlı profilde başlatılamaz.")

    existing = getattr(parent, "_neto_automation_panel", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.pack(fill="both", expand=True)
            existing.lift()
            return existing
    except Exception:
        parent._neto_automation_panel = None

    controller = AutomationPanel(
        parent,
        root=root,
        palette_getter=palette_getter,
        close_command=close_command,
    )
    frame = controller.widget()
    setattr(frame, "_neto_automation_controller", controller)
    setattr(frame, "_neto_automation_cleanup", controller.cleanup)
    setattr(frame, "_neto_surface_role", "automation_panel")
    parent._neto_automation_panel = frame
    return frame


__all__ = ["AutomationPanel", "create_automation_panel"]
