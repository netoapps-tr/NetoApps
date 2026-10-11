from __future__ import annotations

import threading
import subprocess
from pathlib import Path
from typing import Any, Optional, cast

import customtkinter as ctk

from neto_motion_engine_v2 import get_motion_engine
from neto_runtime_policy_v2 import (
    animation_label,
    animation_mode,
    motion_preferences,
    set_animation_mode,
    show_toast,
)

BUILD = "23.0-animation-performance-only-ui"

DEFAULT_PALETTE = {
    "bg": "#09090B",
    "sidebar": "#1A1A1F",
    "card": "#1B1B20",
    "entry": "#141418",
    "border": "#383841",
    "text": "#F5F5F7",
    "muted": "#AAAABD",
    "accent": "#22C55E",
    "hover": "#292930",
    "switch_off": "#41414B",
}


def _palette(value: Optional[dict]) -> dict:
    result = dict(DEFAULT_PALETTE)
    if isinstance(value, dict):
        aliases = {
            "entry_bg": "entry",
            "entry_border": "border",
            "text_main": "text",
            "text_dim": "muted",
            "neon": "accent",
            "button_hover": "hover",
        }
        for key, item in value.items():
            target = aliases.get(key, key)
            if target in result and isinstance(item, str) and item:
                result[target] = item
    return result


def _runtime():
    try:
        from neto_runtime_core import get_runtime
        return get_runtime()
    except Exception:
        return None


class RuntimeControlPanel:
    def __init__(self, parent, root=None, palette=None, lang="tr", project_dir=None):
        self.parent = parent
        self.root = root or parent.winfo_toplevel()
        self.palette = _palette(palette)
        self.lang = "en" if str(lang).lower().startswith("en") else "tr"
        self.project_dir = Path(project_dir or Path(__file__).resolve().parent)
        self.motion = get_motion_engine(self.root)
        self.mode_selector = None
        self.mode_description = None
        self.motion_progress = None
        self.motion_status = None
        self.runtime_status = None
        self.wsl_status = None
        self.ollama_status = None
        self._alive = True
        self._refresh_token = 0
        self.container = ctk.CTkFrame(parent, fg_color="transparent")
        self.container.bind("<Destroy>", self._on_destroy, add="+")
        self.container.pack(fill="both", expand=True)
        self._build()
        try:
            self.root.after(50, self.refresh_async)
        except Exception:
            self.refresh_async()

    def _on_destroy(self, event=None):
        if event is not None and getattr(event, "widget", None) is not self.container:
            return
        self._alive = False
        self._refresh_token += 1

    def _widget_alive(self, widget) -> bool:
        try:
            return bool(self._alive and widget is not None and widget.winfo_exists())
        except Exception:
            return False

    def _safe_configure(self, widget, **kwargs) -> bool:
        if not self._widget_alive(widget):
            return False
        try:
            widget.configure(**kwargs)
            return True
        except Exception:
            return False

    def _tr(self, tr: str, en: str) -> str:
        return tr if self.lang == "tr" else en

    def _card(self):
        p = self.palette
        card = ctk.CTkFrame(
            self.container,
            fg_color=p["card"],
            border_width=1,
            border_color=p["border"],
            corner_radius=17,
        )
        card.pack(fill="x", padx=13, pady=(0, 13))
        return card

    def _card_title(self, card, title: str, description: str = ""):
        p = self.palette
        ctk.CTkLabel(
            card,
            text=title,
            text_color=p["text"],
            font=("Segoe UI Semibold", 15),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(15, 0))
        if description:
            ctk.CTkLabel(
                card,
                text=description,
                text_color=p["muted"],
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
                wraplength=720,
            ).pack(fill="x", padx=16, pady=(4, 12))

    def _button(self, parent, text, command, *, width=130, primary=False):
        p = self.palette
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=34,
            corner_radius=9,
            fg_color=p["accent"] if primary else p["entry"],
            hover_color="#16A34A" if primary else p["hover"],
            text_color="#06110A" if primary else p["text"],
            border_width=0 if primary else 1,
            border_color=p["border"],
            font=("Segoe UI Semibold", 10),
        )

    def _build(self):
        p = self.palette
        ctk.CTkLabel(
            self.container,
            text=self._tr("Sistem ve Performans", "System and Performance"),
            text_color=p["text"],
            font=("Segoe UI Semibold", 23),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(
            self.container,
            text=self._tr(
                "Performans profilleri kaldırıldı. Buradaki performans ayarı yalnızca arayüz animasyonlarını etkiler.",
                "Performance profiles were removed. The setting here affects only interface animations.",
            ),
            text_color=p["muted"],
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            wraplength=720,
        ).pack(fill="x", padx=15, pady=(4, 15))

        self._build_animation_card()
        self._build_runtime_card()
        self._build_wsl_card()
        self._build_ollama_card()

    def _build_animation_card(self):
        p = self.palette
        card = self._card()
        self._card_title(
            card,
            self._tr("Animasyon performansı", "Animation performance"),
            self._tr(
                "Bu seçenek servisleri ve özellikleri kapatmaz; yalnızca geçiş, kayma, renk ve yazı animasyonlarının yükünü değiştirir.",
                "This does not disable services or features; it only changes the cost of transitions, slides, colors, and text motion.",
            ),
        )

        values = [
            self._tr("Normal", "Normal"),
            self._tr("Azaltılmış", "Reduced"),
            self._tr("Kapalı", "Off"),
        ]
        self._display_to_mode = {
            values[0]: "normal",
            values[1]: "reduced",
            values[2]: "off",
        }
        self._mode_to_display = {value: key for key, value in self._display_to_mode.items()}

        self.mode_selector = ctk.CTkSegmentedButton(
            card,
            values=values,
            selected_color=p["accent"],
            selected_hover_color="#16A34A",
            unselected_color=p["entry"],
            unselected_hover_color=p["hover"],
            text_color=p["text"],
            font=("Segoe UI Semibold", 10),
            command=self._on_mode_changed,
        )
        self.mode_selector.pack(fill="x", padx=16, pady=(0, 10))

        self.mode_description = ctk.CTkLabel(
            card,
            text="",
            text_color=p["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.mode_description.pack(fill="x", padx=16, pady=(0, 12))

        demo = ctk.CTkFrame(card, fg_color=p["entry"], corner_radius=12)
        demo.pack(fill="x", padx=16, pady=(0, 14))
        self.motion_progress = ctk.CTkProgressBar(
            demo,
            height=9,
            progress_color=p["accent"],
            fg_color="#2B2B32",
            corner_radius=5,
        )
        self.motion_progress.pack(fill="x", padx=13, pady=(13, 7))
        self.motion_progress.set(0.0)
        self.motion_status = ctk.CTkLabel(
            demo,
            text="",
            text_color=p["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.motion_status.pack(fill="x", padx=13, pady=(0, 9))
        self._button(
            demo,
            self._tr("Animasyonu test et", "Test animation"),
            self.test_motion,
            width=145,
            primary=True,
        ).pack(anchor="w", padx=13, pady=(0, 13))

    def _build_runtime_card(self):
        p = self.palette
        card = self._card()
        self._card_title(
            card,
            self._tr("Çalışma durumu", "Runtime status"),
            self._tr(
                "Özellikler artık performans profiline göre engellenmez.",
                "Features are no longer blocked by a performance profile.",
            ),
        )
        self.runtime_status = ctk.CTkLabel(
            card,
            text=self._tr("Kontrol ediliyor...", "Checking..."),
            text_color=p["muted"],
            font=("Consolas", 10),
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.runtime_status.pack(fill="x", padx=16, pady=(0, 10))
        self._button(card, self._tr("Durumu yenile", "Refresh status"), self.refresh, width=130).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_wsl_card(self):
        p = self.palette
        card = self._card()
        self._card_title(
            card,
            self._tr("Linux köprüsü (WSL)", "Linux bridge (WSL)"),
            self._tr(
                "Windows içinden Linux araçlarını çalıştırmak için hafif bir WSL köprüsü.",
                "A lightweight WSL bridge for running Linux tools from Windows.",
            ),
        )
        self.wsl_status = ctk.CTkLabel(
            card,
            text=self._tr("Kontrol ediliyor...", "Checking..."),
            text_color=p["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.wsl_status.pack(fill="x", padx=16, pady=(0, 10))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 14))
        self._button(actions, self._tr("Yenile", "Refresh"), self.refresh_wsl, width=120).pack(side="left")
        self._button(actions, self._tr("Etkinleştir", "Enable"), self.start_wsl_bridge, width=132, primary=True).pack(side="left", padx=8)
        self._button(actions, self._tr("Kapat", "Disable"), self.stop_wsl_bridge, width=120).pack(side="left")
        self._button(actions, self._tr("WSL kabuğunu aç", "Open WSL shell"), self.open_wsl_shell, width=170).pack(side="left", padx=8)

    def _build_ollama_card(self):
        p = self.palette
        card = self._card()
        self._card_title(
            card,
            self._tr("Yerel model", "Local model"),
            self._tr(
                "Ollama Neto açılırken başlatılmaz; yalnızca ihtiyaç anında bağlanır.",
                "Ollama is not started with Neto; it is contacted only when needed.",
            ),
        )
        self.ollama_status = ctk.CTkLabel(
            card,
            text=self._tr("Kontrol ediliyor...", "Checking..."),
            text_color=p["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.ollama_status.pack(fill="x", padx=16, pady=(0, 10))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 14))
        self._button(actions, self._tr("Durumu kontrol et", "Check status"), self.refresh_ollama, width=145).pack(side="left")
        self._button(actions, self._tr("Modeli bellekten çıkar", "Unload model"), self.unload_ollama, width=175).pack(side="left", padx=8)

    def _on_mode_changed(self, display_value: str):
        mode = self._display_to_mode.get(display_value, "normal")
        set_animation_mode(mode)
        self.refresh()
        self.test_motion()

    def _mode_description_text(self, mode: str) -> str:
        if mode == "off":
            return self._tr(
                "Animasyonlar kapalıdır. Arayüz doğrudan son duruma geçer; hiçbir özellik veya servis kapatılmaz.",
                "Animations are off. The UI jumps directly to the final state; no feature or service is disabled.",
            )
        if mode == "reduced":
            return self._tr(
                "Animasyon süreleri yaklaşık %65 kısalır, yaylı geçişler sadeleşir ve hedef kare aralığı düşürülür.",
                "Animation duration is reduced by about 65%, spring motion is simplified, and the frame rate target is lowered.",
            )
        return self._tr(
            "Zamana dayalı akıcı animasyonlar tam süre ve yaklaşık 60 FPS hedefiyle çalışır.",
            "Time-based smooth animations run at full duration with an approximately 60 FPS target.",
        )

    def test_motion(self):
        progress = cast(Any, self.motion_progress)
        status = cast(Any, self.motion_status)
        motion = cast(Any, self.motion)
        root = cast(Any, self.root)
        if not self._widget_alive(progress) or not self._widget_alive(status):
            return
        prefs = motion_preferences()
        mode = prefs.get("mode", "normal")
        progress.set(0.0)
        if mode == "off":
            progress.set(1.0)
            self._safe_configure(status, text=self._tr("Animasyon kapalı; sonuç doğrudan gösterildi.", "Animation is off; the final state was shown immediately."))
            return
        self._safe_configure(status, text=self._tr("Animasyon testi çalışıyor…", "Animation test is running…"))
        motion.progress_bar(progress, start=0.0, end=1.0, duration_ms=850, key="settings-animation-performance-test")
        delay = 420 if mode == "reduced" else 900
        root.after(delay, lambda: self._safe_configure(status, text=self._tr("Animasyon testi tamamlandı.", "Animation test completed.")))

    def refresh_ollama(self):
        status = cast(Any, self.ollama_status)
        root = cast(Any, self.root)
        self._safe_configure(status, text=self._tr("Kontrol ediliyor…", "Checking…"), text_color=self.palette["muted"])
        def worker():
            try:
                from neto_lazy_ollama_v2 import status
                value = status()
            except Exception as exc:
                value = {"error": str(exc)}
            def update():
                if not self._widget_alive(status):
                    return
                if value.get("error"):
                    self._safe_configure(status, text=str(value["error"]), text_color="#EF4444")
                elif value.get("api_ready") and value.get("model_available"):
                    self._safe_configure(status, text=self._tr("Hazır · gemma3:4b kurulu", "Ready · gemma3:4b installed"), text_color="#22C55E")
                elif value.get("executable"):
                    self._safe_configure(status, text=self._tr("Ollama kurulu; servis şu an kapalı.", "Ollama is installed; the service is currently stopped."), text_color="#F59E0B")
                else:
                    self._safe_configure(status, text=self._tr("Ollama bulunamadı.", "Ollama was not found."), text_color="#EF4444")
            try:
                root.after(0, update)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name="NetoAnimationSettingsOllamaStatus").start()

    def unload_ollama(self):
        root = cast(Any, self.root)
        def worker():
            try:
                from neto_lazy_ollama_v2 import unload_model
                success = bool(unload_model())
            except Exception:
                success = False
            try:
                root.after(0, lambda: show_toast(
                    root,
                    self._tr("Model belleği", "Model memory"),
                    self._tr("gemma3:4b bellekten çıkarıldı." if success else "Model aktif değildi veya çıkarılamadı.", "gemma3:4b was unloaded." if success else "The model was not active or could not be unloaded."),
                    kind="success" if success else "warning",
                ))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name="NetoAnimationSettingsOllamaUnload").start()

    def _wsl_bridge_module(self):
        try:
            import neto_wsl_bridge as bridge
            return bridge
        except Exception:
            return None

    def _wsl_bridge_snapshot(self):
        bridge = self._wsl_bridge_module()
        if bridge is None:
            return {
                "state": "missing",
                "available": False,
                "distros": [],
                "distro": "",
                "running": False,
                "ready": False,
                "last_error": "neto_wsl_bridge.py yüklenemedi.",
                "hint": "",
            }
        try:
            return bridge.status()
        except Exception as exc:
            return {
                "state": "error",
                "available": False,
                "distros": [],
                "distro": "",
                "running": False,
                "ready": False,
                "last_error": str(exc),
                "hint": "",
            }

    def refresh_wsl(self):
        status = cast(Any, self.wsl_status)
        if not self._widget_alive(status):
            return
        self._safe_configure(status, text=self._tr("Kontrol ediliyor...", "Checking..."), text_color=self.palette["muted"])
        threading.Thread(target=self._refresh_wsl_worker, daemon=True, name="NetoSystemSettingsWslStatus").start()

    def _refresh_wsl_worker(self):
        snapshot = self._wsl_bridge_snapshot()
        runtime = _runtime()
        service_state = ""
        if runtime is not None:
            try:
                runtime_snapshot = runtime.status()
                services = runtime_snapshot.get("services", []) if isinstance(runtime_snapshot, dict) else []
                for item in services:
                    if str(item.get("name")) == "linux_bridge":
                        service_state = str(item.get("status") or "")
                        break
            except Exception:
                pass
        try:
            self.root.after(0, lambda: self._apply_wsl_status(snapshot, service_state))
        except Exception:
            pass

    def _apply_wsl_status(self, snapshot, service_state=""):
        status = cast(Any, self.wsl_status)
        if not self._widget_alive(status):
            return
        state = str(snapshot.get("state") or "")
        distros = snapshot.get("distros") or []
        distro_text = ", ".join(str(item) for item in distros if str(item).strip()) or self._tr("yok", "none")
        hint = str(snapshot.get("hint") or "").strip()
        error = str(snapshot.get("last_error") or "").strip()
        endpoint = str(snapshot.get("endpoint") or "").strip()
        port = snapshot.get("port")
        label = ""
        color = self.palette["muted"]
        if state == "running":
            color = "#22C55E"
            distro = str(snapshot.get("distro") or "").strip() or self._tr("varsayılan", "default")
            label = self._tr(
                f"Aktif · {distro} · {endpoint or 'localhost'}",
                f"Active · {distro} · {endpoint or 'localhost'}",
            )
        elif state == "starting":
            color = "#F59E0B"
            distro = str(snapshot.get("distro") or "").strip() or self._tr("varsayılan", "default")
            label = self._tr(
                f"Başlatılıyor · {distro} · port {port or '-'}",
                f"Starting · {distro} · port {port or '-'}",
            )
        elif state == "failed":
            color = "#EF4444"
            label = self._tr("Hata oluştu.", "An error occurred.")
        elif state == "no_distro":
            color = "#F59E0B"
            label = self._tr("WSL var ama dağıtım yok.", "WSL is installed but no distro is available.")
        elif state == "unavailable":
            color = "#EF4444"
            label = self._tr("WSL bulunamadı.", "WSL was not found.")
        else:
            label = self._tr("Kapalı.", "Stopped.")

        lines = [
            label,
            self._tr(f"Dağıtımlar: {distro_text}", f"Distros: {distro_text}"),
        ]
        if service_state:
            lines.append(self._tr(f"Servis durumu: {service_state}", f"Service state: {service_state}"))
        if snapshot.get("assistant_available"):
            lines.append(self._tr("Asistan motoru: hazır", "Assistant engine: ready"))
        if hint:
            lines.append(hint)
        if error and error != hint:
            lines.append(error)
        self._safe_configure(
            status,
            text="\n".join(lines),
            text_color=color,
        )

    def start_wsl_bridge(self):
        root = cast(Any, self.root)

        def worker():
            try:
                runtime = _runtime()
                if runtime is not None:
                    runtime.set_custom_feature("linux_bridge", True)
            except Exception as exc:
                try:
                    root.after(0, lambda: show_toast(
                        root,
                        self._tr("WSL köprüsü", "WSL bridge"),
                        str(exc),
                        kind="error",
                    ))
                except Exception:
                    pass
            try:
                root.after(0, self.refresh_async)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="NetoWslBridgeEnable").start()

    def stop_wsl_bridge(self):
        root = cast(Any, self.root)

        def worker():
            try:
                runtime = _runtime()
                if runtime is not None:
                    runtime.set_custom_feature("linux_bridge", False)
            except Exception as exc:
                try:
                    root.after(0, lambda: show_toast(
                        root,
                        self._tr("WSL köprüsü", "WSL bridge"),
                        str(exc),
                        kind="error",
                    ))
                except Exception:
                    pass
            try:
                root.after(0, self.refresh_async)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="NetoWslBridgeDisable").start()

    def open_wsl_shell(self):
        root = cast(Any, self.root)
        bridge = self._wsl_bridge_module()
        if bridge is None:
            show_toast(
                root,
                self._tr("WSL kabuğu", "WSL shell"),
                self._tr("WSL bridge modülü yüklenemedi.", "WSL bridge module could not be loaded."),
                kind="error",
            )
            return
        try:
            snapshot = self._wsl_bridge_snapshot()
            if not snapshot.get("available") or not snapshot.get("distros"):
                show_toast(
                    root,
                    self._tr("WSL kabuğu", "WSL shell"),
                    self._tr("Önce en az bir WSL dağıtımı yüklemelisin.", "You need to install at least one WSL distro first."),
                    kind="warning",
                )
                return
            if bridge.open_wsl_shell():
                show_toast(
                    root,
                    self._tr("WSL kabuğu", "WSL shell"),
                    self._tr("WSL kabuğu açıldı.", "WSL shell opened."),
                    kind="success",
                )
            else:
                show_toast(
                    root,
                    self._tr("WSL kabuğu", "WSL shell"),
                    self._tr("WSL çalıştırılamadı veya kurulu değil.", "WSL could not be started or is not installed."),
                    kind="warning",
                )
        except Exception as exc:
            show_toast(
                root,
                self._tr("WSL kabuğu", "WSL shell"),
                str(exc),
                kind="error",
            )

    def refresh_async(self):
        self._refresh_token += 1
        self.refresh(render_token=self._refresh_token)

    def refresh(self, render_token=None):
        if not self._alive:
            return
        if render_token is None:
            self._refresh_token += 1
            render_token = self._refresh_token
        mode_selector = cast(Any, self.mode_selector)
        mode_description = cast(Any, self.mode_description)
        motion_status = cast(Any, self.motion_status)
        runtime_status = cast(Any, self.runtime_status)
        wsl_status = cast(Any, self.wsl_status)
        mode = animation_mode()
        try:
            mode_selector.set(self._mode_to_display.get(mode, self._mode_to_display["normal"]))
        except Exception:
            pass
        if mode_description is not None:
            self._safe_configure(mode_description, text=self._mode_description_text(mode))
        if motion_status is not None:
            self._safe_configure(motion_status, text=self._tr(f"Etkin mod: {animation_label(mode, 'tr')}", f"Active mode: {animation_label(mode, 'en')}"))

        if wsl_status is not None:
            self.refresh_wsl()

        if not self._widget_alive(runtime_status):
            return
        self._safe_configure(
            runtime_status,
            text=self._tr("Runtime kontrol ediliyor...", "Checking runtime..."),
            text_color=self.palette["muted"],
        )

        def runtime_worker(token=render_token, current_mode=mode):
            runtime = _runtime()
            color = self.palette["muted"]
            if runtime is None:
                text = self._tr("Runtime bağlantısı kurulamadı.", "Runtime connection unavailable.")
                color = "#F59E0B"
            else:
                try:
                    snapshot = runtime.status()
                    services = snapshot.get("services", []) if isinstance(snapshot, dict) else []
                    running = [str(item.get("name")) for item in services if item.get("status") == "running"]
                    text = self._tr(
                        f"Animasyon modu: {animation_label(current_mode, 'tr')}\nÇalışan servisler: {', '.join(running) if running else 'yok'}\nTüm özellikler performans profilinden bağımsızdır.",
                        f"Animation mode: {animation_label(current_mode, 'en')}\nRunning services: {', '.join(running) if running else 'none'}\nAll features are independent of performance profiles.",
                    )
                except Exception as exc:
                    text = str(exc)
                    color = "#EF4444"

            def apply_result():
                if token != self._refresh_token or not self._widget_alive(runtime_status):
                    return
                self._safe_configure(runtime_status, text=text, text_color=color)

            try:
                self.root.after(0, apply_result)
            except Exception:
                pass

        threading.Thread(target=runtime_worker, daemon=True, name="NetoSystemSettingsRuntimeStatus").start()


def render_system_control(parent, root=None, palette=None, lang="tr", project_dir=None):
    return RuntimeControlPanel(parent=parent, root=root, palette=palette, lang=lang, project_dir=project_dir)
