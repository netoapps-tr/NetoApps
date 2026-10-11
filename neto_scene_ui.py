"""Modern in-app UI for the NetOps v1.39 scene system."""

from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from neto_scene_engine import (
    SceneAdapters,
    SceneError,
    delete_scene,
    duplicate_scene,
    get_scene,
    list_scenes,
    preview_scene,
    run_scene,
    save_scene,
    scene_running,
    stop_scene,
)


PROFILE_LABELS = {
    "balanced": "Dengeli",
    "gaming": "Oyun",
    "study": "Ders",
    "streaming": "Yayın",
    "quiet": "Sessiz",
}


class ScenePalette:
    def __init__(self, getter: Optional[Callable[[], dict[str, str]]]):
        value = getter() if callable(getter) else {}
        self.bg = value.get("bg", "#0B0B0F")
        self.card = value.get("card", "#19191F")
        self.card_2 = value.get("entry_bg", "#101015")
        self.border = value.get("entry_border", "#35353F")
        self.text = value.get("text_main", "#F4F4F5")
        self.muted = value.get("text_dim", "#A1A1AA")
        self.accent = value.get("neon", "#22C55E")
        self.hover = value.get("button_hover", "#292932")
        self.blue = value.get("accent", "#4F7CFF")
        self.yellow = "#F59E0B"
        self.red = "#EF4444"


class SceneEditor:
    def __init__(self, panel: "ScenePanel", scene: Optional[dict[str, Any]] = None):
        self.panel = panel
        self.palette = panel.palette
        self.scene = scene or {
            "name": "Yeni Sahne",
            "description": "Kişisel çalışma alanım.",
            "icon": "NET",
            "custom": True,
            "profile": "balanced",
            "volume": {"percent": 35, "muted": False},
            "brightness": None,
            "power": "none",
            "programs_to_open": [],
            "programs_to_close": [],
            "automations": [],
            "delay_seconds": 0.25,
            "triggers": [],
            "rollback_on_failure": True,
        }
        self.window = ctk.CTkToplevel(panel.root)
        self.window.title("Neto Hazırla · Sahne düzenle")
        self.window.geometry("560x720")
        self.window.minsize(480, 560)
        self.window.configure(fg_color=self.palette.bg)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._build()

    def _label(self, parent, text: str, muted=False):
        return ctk.CTkLabel(
            parent,
            text=text,
            text_color=self.palette.muted if muted else self.palette.text,
            font=("Segoe UI", 10),
            anchor="w",
        )

    def _entry(self, parent, value: Any = "", multiline=False, height=34):
        if multiline:
            widget = ctk.CTkTextbox(
                parent,
                height=height,
                fg_color=self.palette.card_2,
                border_width=1,
                border_color=self.palette.border,
                text_color=self.palette.text,
                wrap="word",
            )
            widget.insert("1.0", str(value or ""))
            return widget
        widget = ctk.CTkEntry(
            parent,
            height=height,
            fg_color=self.palette.card_2,
            border_color=self.palette.border,
            text_color=self.palette.text,
        )
        if value not in (None, ""):
            widget.insert(0, str(value))
        return widget

    def _section(self, parent, title: str):
        box = ctk.CTkFrame(parent, fg_color=self.palette.card, border_width=1, border_color=self.palette.border, corner_radius=12)
        box.pack(fill="x", padx=12, pady=6)
        self._label(box, title).pack(fill="x", padx=12, pady=(10, 4))
        return box

    def _build(self):
        shell = ctk.CTkScrollableFrame(self.window, fg_color=self.palette.bg)
        shell.pack(fill="both", expand=True, padx=8, pady=8)
        identity = self._section(shell, "Sahne kimliği")
        self.name_entry = self._entry(identity, self.scene.get("name"))
        self.name_entry.pack(fill="x", padx=12, pady=3)
        self.description_entry = self._entry(identity, self.scene.get("description"), multiline=True, height=58)
        self.description_entry.pack(fill="x", padx=12, pady=3)
        profile = self._section(shell, "Profil ve ses")
        row = ctk.CTkFrame(profile, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        self._label(row, "Profil").pack(side="left")
        self.profile_var = ctk.StringVar(value=PROFILE_LABELS.get(self.scene.get("profile", "balanced"), "Dengeli"))
        self.profile_menu = ctk.CTkOptionMenu(row, variable=self.profile_var, values=list(PROFILE_LABELS.values()), fg_color=self.palette.card_2, button_color=self.palette.accent, button_hover_color=self.palette.hover, text_color=self.palette.text)
        self.profile_menu.pack(side="right", fill="x", expand=True, padx=(16, 0))
        volume = self.scene.get("volume") or {}
        self.volume_entry = self._entry(profile, volume.get("percent", 35))
        self._label(profile, "Ses seviyesi (0-100)", muted=True).pack(fill="x", padx=12, pady=(7, 0))
        self.volume_entry.pack(fill="x", padx=12, pady=3)
        self.muted_var = ctk.BooleanVar(value=bool(volume.get("muted", False)))
        ctk.CTkCheckBox(profile, text="Sessiz modu etkinleştir", variable=self.muted_var, text_color=self.palette.text, fg_color=self.palette.accent, hover_color=self.palette.hover).pack(anchor="w", padx=12, pady=5)
        system = self._section(shell, "Programlar ve ekran")
        self._label(system, "Açılacak programlar (her satırda tam yol)", muted=True).pack(fill="x", padx=12)
        self.open_entry = self._entry(system, "\n".join(item.get("path", "") for item in self.scene.get("programs_to_open", [])), multiline=True, height=64)
        self.open_entry.pack(fill="x", padx=12, pady=3)
        self._label(system, "Normal kapatılacak program adları", muted=True).pack(fill="x", padx=12, pady=(4, 0))
        self.close_entry = self._entry(system, "\n".join(self.scene.get("programs_to_close", [])), multiline=True, height=55)
        self.close_entry.pack(fill="x", padx=12, pady=3)
        self._label(system, "Parlaklık (boş bırakılabilir)", muted=True).pack(fill="x", padx=12, pady=(4, 0))
        self.brightness_entry = self._entry(system, self.scene.get("brightness", ""))
        self.brightness_entry.pack(fill="x", padx=12, pady=3)
        power = self._section(shell, "Gecikme ve güç güvenliği")
        self._label(power, "Adımlar arası gecikme (saniye)", muted=True).pack(fill="x", padx=12)
        self.delay_entry = self._entry(power, self.scene.get("delay_seconds", 0.25))
        self.delay_entry.pack(fill="x", padx=12, pady=3)
        self.power_var = ctk.StringVar(value=self.scene.get("power", "none"))
        self.power_menu = ctk.CTkOptionMenu(power, variable=self.power_var, values=["none", "display_off", "sleep", "shutdown"], fg_color=self.palette.card_2, button_color=self.palette.accent, button_hover_color=self.palette.hover, text_color=self.palette.text)
        self.power_menu.pack(fill="x", padx=12, pady=5)
        self._label(power, "Uyku/kapatma seçersen çalıştırmadan önce onay alınır.", muted=True).pack(fill="x", padx=12, pady=(0, 7))
        trigger = self._section(shell, "Otomatik tetikleyici")
        trigger_values = {"manual": "Manuel", "startup": "Neto açıldığında", "daily": "Her gün", "process_open": "Program açıldığında"}
        current_trigger = (self.scene.get("triggers") or [{}])[0]
        current_type = current_trigger.get("type", "manual")
        self.trigger_type_map = trigger_values
        self.trigger_reverse = {label: key for key, label in trigger_values.items()}
        self.trigger_var = ctk.StringVar(value=trigger_values.get(current_type, "Manuel"))
        self.trigger_menu = ctk.CTkOptionMenu(trigger, variable=self.trigger_var, values=list(trigger_values.values()), fg_color=self.palette.card_2, button_color=self.palette.accent, button_hover_color=self.palette.hover, text_color=self.palette.text)
        self.trigger_menu.pack(fill="x", padx=12, pady=4)
        trigger_value = ""
        if current_type == "startup":
            trigger_value = current_trigger.get("delay_seconds", 5)
        elif current_type == "daily":
            trigger_value = current_trigger.get("time", "23:00")
        elif current_type == "process_open":
            trigger_value = current_trigger.get("process_name", "notepad.exe")
        self.trigger_value_entry = self._entry(trigger, trigger_value)
        self.trigger_value_entry.pack(fill="x", padx=12, pady=4)
        self._label(trigger, "Manuel için boş bırak. Açılışta gecikme, günlükte saat, programda exe adı yaz.", muted=True).pack(fill="x", padx=12, pady=(0, 8))
        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(10, 18))
        ctk.CTkButton(footer, text="İptal", width=84, fg_color=self.palette.card, hover_color=self.palette.hover, border_width=1, border_color=self.palette.border, command=self.close).pack(side="right", padx=4)
        ctk.CTkButton(footer, text="Kaydet", width=100, fg_color=self.palette.accent, hover_color="#16A34A", text_color="#06110A", command=self.save).pack(side="right", padx=4)

    @staticmethod
    def _text(widget) -> str:
        if isinstance(widget, ctk.CTkTextbox):
            return widget.get("1.0", "end-1c").strip()
        return widget.get().strip()

    def save(self):
        try:
            profile = next(key for key, label in PROFILE_LABELS.items() if label == self.profile_var.get())
            opened = [{"path": line.strip(), "args": [], "cwd": ""} for line in self._text(self.open_entry).splitlines() if line.strip()]
            trigger_type = self.trigger_reverse.get(self.trigger_var.get(), "manual")
            trigger_value = self._text(self.trigger_value_entry)
            triggers = []
            if trigger_type == "startup" and trigger_value:
                triggers = [{"type": "startup", "delay_seconds": int(float(trigger_value))}]
            elif trigger_type == "daily" and trigger_value:
                triggers = [{"type": "daily", "time": trigger_value}]
            elif trigger_type == "process_open" and trigger_value:
                triggers = [{"type": "process_open", "process_name": trigger_value}]
            scene = dict(self.scene)
            scene.update(
                {
                    "name": self._text(self.name_entry),
                    "description": self._text(self.description_entry),
                    "profile": profile,
                    "volume": {"percent": int(float(self._text(self.volume_entry) or 0)), "muted": bool(self.muted_var.get())},
                    "brightness": self._text(self.brightness_entry) or None,
                    "delay_seconds": float(self._text(self.delay_entry) or 0.25),
                    "power": self.power_var.get(),
                    "programs_to_open": opened,
                    "programs_to_close": [line.strip() for line in self._text(self.close_entry).splitlines() if line.strip()],
                    "triggers": triggers,
                    "custom": True,
                }
            )
            saved = save_scene(scene)
        except Exception as exc:
            messagebox.showerror("Sahne", str(exc), parent=self.window)
            return
        self.panel.selected_id = saved["id"]
        self.close()
        self.panel.refresh()

    def close(self):
        try:
            self.window.destroy()
        except Exception:
            pass


class ScenePanel:
    def __init__(self, parent, *, root=None, palette_getter=None, close_command=None, adapters_getter=None):
        self.parent = parent
        self.root = root or parent.winfo_toplevel()
        self.close_command = close_command
        self.adapters_getter = adapters_getter
        self.palette = ScenePalette(palette_getter)
        self.closed = False
        self.selected_id: Optional[str] = None
        self.refresh_job = None
        self.run_buttons: list[Any] = []
        self.frame = ctk.CTkFrame(parent, fg_color=self.palette.bg, corner_radius=0)
        self.frame.pack(fill="both", expand=True)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_body()
        self.refresh()

    def _button(self, parent, text, command, width=90, primary=False, danger=False):
        fg = self.palette.red if danger else (self.palette.accent if primary else self.palette.card_2)
        hover = "#DC2626" if danger else ("#16A34A" if primary else self.palette.hover)
        return ctk.CTkButton(parent, text=text, width=width, height=34, corner_radius=9, fg_color=fg, hover_color=hover, text_color="#06110A" if primary else self.palette.text, border_width=0 if (primary or danger) else 1, border_color=self.palette.border, font=("Segoe UI Semibold", 9), command=command)

    def _build_header(self):
        header = ctk.CTkFrame(self.frame, height=72, fg_color=self.palette.card, border_width=1, border_color=self.palette.border, corner_radius=14)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)
        badge = ctk.CTkLabel(header, text="N", width=46, height=46, fg_color=self.palette.accent, text_color="#06110A", corner_radius=23, font=("Segoe UI Semibold", 16))
        badge.grid(row=0, column=0, padx=(12, 10), pady=12)
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="ew", padx=3)
        ctk.CTkLabel(title_box, text="Neto Hazırla", text_color=self.palette.text, font=("Segoe UI Semibold", 21), anchor="w").pack(fill="x", pady=(7, 0))
        self.status_label = ctk.CTkLabel(title_box, text="Tek tuşla güvenli çalışma alanı", text_color=self.palette.muted, font=("Segoe UI", 9), anchor="w")
        self.status_label.pack(fill="x", pady=(0, 5))
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(5, 12), pady=10)
        self._button(actions, "+ Yeni", self.new_scene, 62, primary=True).pack(side="left", padx=2)
        self._button(actions, "Yenile", self.refresh, 58).pack(side="left", padx=2)
        if callable(self.close_command):
            self._button(actions, "‹ Geri", self.close_command, 55).pack(side="left", padx=(5, 0))

    def _build_body(self):
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        try:
            narrow = int(self.root.winfo_width()) < 900
        except Exception:
            narrow = False
        body.grid_columnconfigure(0, weight=0, minsize=170 if narrow else 250)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(body, fg_color=self.palette.card, border_width=1, border_color=self.palette.border, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left, text="HAZIR SAHNELER", text_color=self.palette.muted, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", padx=13, pady=(13, 7))
        self.list_frame = ctk.CTkScrollableFrame(left, fg_color=self.palette.card_2, corner_radius=10)
        self.list_frame.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        right = ctk.CTkFrame(body, fg_color=self.palette.card, border_width=1, border_color=self.palette.border, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.detail_title = ctk.CTkLabel(right, text="Bir sahne seç", text_color=self.palette.text, font=("Segoe UI Semibold", 20), anchor="w")
        self.detail_title.grid(row=0, column=0, sticky="ew", padx=16, pady=(15, 0))
        self.detail_desc = ctk.CTkLabel(right, text="", text_color=self.palette.muted, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=600)
        self.detail_desc.grid(row=1, column=0, sticky="ew", padx=16, pady=(3, 10))
        self.timeline = ctk.CTkScrollableFrame(right, fg_color=self.palette.card_2, corner_radius=11)
        self.timeline.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))
        bar = ctk.CTkFrame(right, fg_color=self.palette.card_2, border_width=1, border_color=self.palette.border, corner_radius=18, height=56)
        bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        bar.grid_propagate(False)
        self._button(bar, "Önizle", self.preview_selected, 72).pack(side="left", padx=(10, 4), pady=10)
        self._button(bar, "Kopyala", self.copy_selected, 74).pack(side="left", padx=4, pady=10)
        self._button(bar, "Düzenle", self.edit_selected, 72).pack(side="left", padx=4, pady=10)
        self._button(bar, "Sil", self.delete_selected, 52, danger=True).pack(side="right", padx=3, pady=10)
        self._button(bar, "Durdur", self.stop_selected, 68, danger=True).pack(side="right", padx=3, pady=10)
        self.run_button = self._button(bar, "Neto Hazırla", self.run_selected, 108, primary=True)
        self.run_button.pack(side="right", padx=4, pady=10)
        self.run_buttons.append(self.run_button)

    def refresh(self):
        if self.closed:
            return
        scenes = list_scenes()
        for child in self.list_frame.winfo_children():
            child.destroy()
        if self.selected_id not in {item["id"] for item in scenes}:
            self.selected_id = scenes[0]["id"] if scenes else None
        for scene in scenes:
            selected = scene["id"] == self.selected_id
            card = ctk.CTkFrame(self.list_frame, fg_color=self.palette.accent if selected else self.palette.card, border_width=1, border_color=self.palette.accent if selected else self.palette.border, corner_radius=11, cursor="hand2")
            card.pack(fill="x", padx=3, pady=4)
            card.bind("<Button-1>", lambda _event, sid=scene["id"]: self.select_scene(sid))
            ctk.CTkLabel(card, text=scene.get("icon", "NET"), width=36, height=36, fg_color=self.palette.card_2 if selected else self.palette.card_2, corner_radius=18, text_color=self.palette.text, font=("Segoe UI Semibold", 9)).pack(side="left", padx=(8, 7), pady=8)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, pady=7)
            ctk.CTkLabel(text, text=scene["name"], text_color="#06110A" if selected else self.palette.text, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
            ctk.CTkLabel(text, text="Özel sahne" if scene.get("custom") else "Hazır sahne", text_color="#0B2615" if selected else self.palette.muted, font=("Segoe UI", 8), anchor="w").pack(fill="x")
            for widget in (text, *text.winfo_children()):
                widget.bind("<Button-1>", lambda _event, sid=scene["id"]: self.select_scene(sid))
        self.render_detail()

    def select_scene(self, scene_id: str):
        self.selected_id = scene_id
        self.refresh()

    def render_detail(self):
        if not self.selected_id:
            return
        scene = get_scene(self.selected_id)
        self.detail_title.configure(text=f"{scene.get('icon', 'NET')}  {scene['name']}")
        self.detail_desc.configure(text=scene.get("description") or "Bu sahne için açıklama eklenmemiş.")
        for child in self.timeline.winfo_children():
            child.destroy()
        plan = preview_scene(scene)
        ctk.CTkLabel(self.timeline, text="ÇALIŞMA PLANI", text_color=self.palette.muted, font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x", padx=12, pady=(12, 6))
        for index, step in enumerate(plan["steps"], 1):
            color = self.palette.red if step["risk"] == "danger" else (self.palette.yellow if step["risk"] == "warning" else self.palette.accent)
            row = ctk.CTkFrame(self.timeline, fg_color=self.palette.card, border_width=1, border_color=self.palette.border, corner_radius=9)
            row.pack(fill="x", padx=9, pady=3)
            ctk.CTkLabel(row, text=str(index), width=28, height=28, fg_color=color, text_color="#07110A", corner_radius=14, font=("Segoe UI Semibold", 9)).pack(side="left", padx=(8, 9), pady=7)
            ctk.CTkLabel(row, text=step["label"], text_color=self.palette.text, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=560).pack(side="left", fill="x", expand=True, padx=(0, 10), pady=8)
        if plan["warnings"]:
            ctk.CTkLabel(self.timeline, text="Güvenlik notu: " + " ".join(plan["warnings"]), text_color=self.palette.yellow, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=600).pack(fill="x", padx=12, pady=(10, 12))
        else:
            ctk.CTkLabel(self.timeline, text="Bu sahne yalnızca güvenli ve geri alınabilir ayarlar içeriyor.", text_color=self.palette.muted, font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=12, pady=(10, 12))

    def preview_selected(self):
        if not self.selected_id:
            return
        plan = preview_scene(self.selected_id)
        lines = [f"{plan['scene']['name']} önizlemesi", "", "İşlemler:"]
        lines.extend(f"{index}. {step['label']}" for index, step in enumerate(plan["steps"], 1))
        if plan["warnings"]:
            lines.extend(["", "Güvenlik notları:", *plan["warnings"]])
        messagebox.showinfo("Neto Hazırla · Önizleme", "\n".join(lines), parent=self.root)

    def run_selected(self):
        if not self.selected_id or scene_running():
            return
        plan = preview_scene(self.selected_id)
        if plan["requires_confirmation"] and not messagebox.askyesno("Neto Hazırla", "Bu sahne program kapatma veya güç işlemi içeriyor. Devam edilsin mi?", parent=self.root, icon="warning"):
            return
        scene_id = self.selected_id
        self.status_label.configure(text="Sahne hazırlanıyor…", text_color=self.palette.blue)
        self.run_button.configure(state="disabled")
        adapters = self.adapters_getter() if callable(self.adapters_getter) else None
        thread = threading.Thread(target=self._run_thread, args=(scene_id, adapters), daemon=True, name="NetoSceneRun")
        thread.start()

    def _run_thread(self, scene_id, adapters):
        result = run_scene(scene_id, adapters=adapters, confirm=lambda _message: True, on_progress=self._progress)
        try:
            self.root.after(0, lambda: self._finish_run(result))
        except Exception:
            pass

    def _progress(self, payload):
        try:
            if payload.get("event") == "step_started":
                self.root.after(0, lambda: self.status_label.configure(text=f"Uygulanıyor · {payload.get('label', '')}", text_color=self.palette.blue))
        except Exception:
            pass

    def _finish_run(self, result):
        status = result.get("status")
        if status == "success":
            message = "Sahne hazır."
            color = self.palette.accent
        elif status == "cancelled":
            message = "Sahne durduruldu; güvenli geri dönüş yapıldı."
            color = self.palette.yellow
        else:
            message = f"Sahne tamamlanamadı: {result.get('error') or 'Bilinmeyen hata'}"
            color = self.palette.red
        self.status_label.configure(text=message, text_color=color)
        self.run_button.configure(state="normal")
        self.render_detail()

    def stop_selected(self):
        if stop_scene():
            self.status_label.configure(text="Durdurma istendi…", text_color=self.palette.yellow)

    def new_scene(self):
        SceneEditor(self)

    def copy_selected(self):
        if not self.selected_id:
            return
        try:
            copied = duplicate_scene(self.selected_id)
            self.selected_id = copied["id"]
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Sahne", str(exc), parent=self.root)

    def delete_selected(self):
        if not self.selected_id:
            return
        scene = get_scene(self.selected_id)
        if not scene.get("custom"):
            messagebox.showinfo("Sahne", "Hazır sahneler silinemez. Kopyalayıp kendi sahneni silebilirsin.", parent=self.root)
            return
        if not messagebox.askyesno("Sahneyi sil", f"{scene['name']} silinsin mi?", parent=self.root, icon="warning"):
            return
        try:
            delete_scene(scene["id"])
            self.selected_id = None
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Sahne", str(exc), parent=self.root)

    def edit_selected(self):
        if self.selected_id:
            SceneEditor(self, get_scene(self.selected_id))

    def cleanup(self):
        self.closed = True
        try:
            if scene_running():
                stop_scene()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass


def create_scene_panel(parent, *, root=None, palette_getter=None, close_command=None, adapters_getter=None):
    existing = getattr(parent, "_neto_scene_panel", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.pack(fill="both", expand=True)
            existing.lift()
            return existing
    except Exception:
        pass
    controller = ScenePanel(parent, root=root, palette_getter=palette_getter, close_command=close_command, adapters_getter=adapters_getter)
    frame = controller.frame
    frame._neto_scene_controller = controller
    parent._neto_scene_panel = frame
    return frame


__all__ = ["ScenePanel", "create_scene_panel"]
