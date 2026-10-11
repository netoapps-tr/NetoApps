import json
import os
import os
import platform
import sys
import threading
import time
from typing import Any

import customtkinter as ctk
from PIL import Image

from lang import T, get_lang

import neto_ai
from neto_ai import neto_ai_cevap_ver

try:
    from config import get_data_path
except Exception:
    def get_data_path(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _chat_lang() -> str:
    return "tr" if str(get_lang()).lower().startswith("tr") else "en"


_CHAT_TEXTS = {
    "tr": {
        "chat_title": "NetOps Web Sohbeti",
        "chat_welcome": "Merhaba! Sohbet etmek için yazabilirsin. `.agent` ile web tabanlı karar modunu aç.",
        "chat_model_k2_enabled": "NetOps Agent K2 etkinleştirildi.",
        "chat_model_k1_enabled": "NetOps Agent K1 etkinleştirildi.",
        "chat_install_ai": "Web Sohbeti",
        "chat_error": "Hata: {error}",
        "chat_thinking": "Düşünüyor...",
        "chat_user": "Kullanıcı",
        "chat_ai": "Web Cevap",
        "chat_system": "Sistem",
        "chat_input_placeholder": "Mesajını yaz...",
        "chat_beta_note": "Bu özellik betadadır.",
        "chat_agent_prompt": "Agent açık. Bana yaz, ben web tabanlı cevap vereyim. Kapatmak için n.ext kullan.",
        "chat_agent_placeholder": "Sorunu yaz...",
        "chat_agent_launching": "AI düşünüyor...",
        "chat_agent_opened": "Agent modu aktif.",
        "chat_agent_error": "Agent yanıt veremedi: {error}",
        "chat_agent_busy": "Agent düşünüyor...",
        "chat_agent_window_not_supported": "Bu özellik şu an yalnızca Windows'ta çalışır.",
        "chat_agent_sound_missing": "Ses bulunamadı.",
    },
    "en": {
        "chat_title": "NetOps Web Chat",
        "chat_welcome": "Hello! You can chat here. Use `.agent` to open the web-based decision mode.",
        "chat_model_k2_enabled": "NetOps Agent K2 enabled.",
        "chat_model_k1_enabled": "NetOps Agent K1 enabled.",
        "chat_install_ai": "Web Chat",
        "chat_error": "Error: {error}",
        "chat_thinking": "Thinking...",
        "chat_user": "User",
        "chat_ai": "Web Reply",
        "chat_system": "System",
        "chat_input_placeholder": "Type your message...",
        "chat_beta_note": "This feature is in beta.",
        "chat_agent_prompt": "Agent is on. Type to chat with the web-based reply engine. Use n.ext to close.",
        "chat_agent_placeholder": "Type your question...",
        "chat_agent_launching": "AI is thinking...",
        "chat_agent_opened": "Agent mode active.",
        "chat_agent_error": "Agent could not respond: {error}",
        "chat_agent_busy": "Agent is thinking...",
        "chat_agent_window_not_supported": "This feature currently works only on Windows.",
        "chat_agent_sound_missing": "Sound file not found.",
    },
}


def _chat_text(key: str, **kwargs) -> str:
    lang = _chat_lang()
    text = _CHAT_TEXTS.get(lang, _CHAT_TEXTS["en"]).get(key)
    if text is None:
        text = T(key, **kwargs)
    if kwargs:
        try:
            text = str(text).format(**kwargs)
        except Exception:
            pass
    return str(text)


def _first_existing_path(*names: str) -> str | None:
    for name in names:
        path = resource_path(name)
        if os.path.exists(path):
            return path
    return None


def _play_sound_async(path: str | None) -> None:
    if not path:
        return

    def worker() -> None:
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.Sound(path).play()
        except Exception:
            try:
                if os.name == "nt":
                    import winsound

                    winsound.MessageBeep()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="NetoChatAgentSound").start()


def _focus_safe(widget, *, force: bool = False) -> None:
    try:
        if widget is None:
            return
        exists = getattr(widget, "winfo_exists", None)
        if callable(exists) and not exists():
            return
        if force and hasattr(widget, "focus_force"):
            widget.focus_force()
        elif hasattr(widget, "focus_set"):
            widget.focus_set()
        elif hasattr(widget, "focus"):
            widget.focus()
    except Exception:
        pass


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red, green, blue


def _mix_color(start: str, end: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    sr, sg, sb = _hex_to_rgb(start)
    er, eg, eb = _hex_to_rgb(end)
    rr = round(sr + ((er - sr) * ratio))
    rg = round(sg + ((eg - sg) * ratio))
    rb = round(sb + ((eb - sb) * ratio))
    return f"#{rr:02x}{rg:02x}{rb:02x}"


def resource_path(filename):
    """PyInstaller EXE içinde ve normal Python çalıştırmada dosya yolu bulur."""
    base_path = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, filename)


CHAT_HISTORY_PATH = get_data_path("chat_history.json")
CHAT_HISTORY_LIMIT = 300


def _chat_history_varsayilan():
    return {"version": 1, "messages": []}


def _chat_history_oku():
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, list):
            return {"version": 1, "messages": loaded}
        if isinstance(loaded, dict):
            messages = loaded.get("messages", [])
            if isinstance(messages, list):
                return {"version": int(loaded.get("version", 1) or 1), "messages": messages}
    except Exception:
        pass
    return _chat_history_varsayilan()


def _chat_history_kaydet(data):
    try:
        os.makedirs(os.path.dirname(CHAT_HISTORY_PATH), exist_ok=True)
    except Exception:
        pass

    try:
        temiz = {"version": 1, "messages": []}
        mesajlar = data.get("messages", []) if isinstance(data, dict) else []
        for item in list(mesajlar)[-CHAT_HISTORY_LIMIT:]:
            if not isinstance(item, dict):
                continue
            temiz["messages"].append(
                {
                    "role": str(item.get("role", "system")),
                    "text": str(item.get("text", "")),
                    "ts": float(item.get("ts", time.time())),
                }
            )
        with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(temiz, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_NETO_CHAT_WINDOW: "NetoChatWindow | None" = None


class NetoChatWindow:
    def __init__(self, root, acilis_mesaji: str | None = None):
        global _NETO_CHAT_WINDOW

        self.root = root
        self.waiting = False
        self.agent_mode = False
        self.agent_flash_job = None
        self.agent_queue_job = None
        self.chat_history_data = _chat_history_oku()
        self.header = None
        self.input_frame = None
        self.beta_label = None
        self.logo_image = None
        self._theme = {
            "window": "#151515",
            "header": "#1f1f1f",
            "card": "#202020",
            "entry": "#2a2a2a",
            "entry_border": "#3a3a3a",
            "border": "#333333",
            "button": "#0e639c",
            "button_hover": "#1177bb",
            "button_text": "#ffffff",
            "accent": "#b57cff",
            "accent_dark": "#3a1d67",
            "accent_glow": "#f0d7ff",
        }
        self._agent_theme = {
            "window": "#110f1b",
            "header": "#2a164b",
            "card": "#1a1328",
            "entry": "#2b1c3f",
            "entry_border": "#c084fc",
            "border": "#8b5cf6",
            "button": "#8b5cf6",
            "button_hover": "#a855f7",
            "button_text": "#ffffff",
            "accent": "#f5d0fe",
            "accent_dark": "#4c1d95",
            "accent_glow": "#f0abfc",
        }

        self.chat = ctk.CTkToplevel(root)
        self.chat.title(f"{_chat_text('chat_title')} v1.37")
        self.chat.geometry("700x560")
        self.chat.configure(fg_color=self._theme["window"])
        self.chat.resizable(True, True)
        try:
            self.chat.lift()
            _focus_safe(self.chat, force=True)
        except Exception:
            _focus_safe(self.chat)

        self.chat.protocol("WM_DELETE_WINDOW", self._kapat)
        self._icon_ayarla()
        self._arayuz_olustur()
        self._sohbet_gecmisini_goster()
        if not self.chat_history_data.get("messages"):
            self._mesaj_yaz("ai", _chat_text("chat_welcome"), kaydet=True)
        if acilis_mesaji:
            self._mesaj_yaz("system", acilis_mesaji, kaydet=True)
            self._durum_yaz(acilis_mesaji, "#ffcc66")
        _NETO_CHAT_WINDOW = self

    def _kapat(self):
        global _NETO_CHAT_WINDOW
        try:
            if self.agent_flash_job is not None:
                self.chat.after_cancel(self.agent_flash_job)
        except Exception:
            pass
        try:
            if self.agent_queue_job is not None:
                self.chat.after_cancel(self.agent_queue_job)
        except Exception:
            pass
        try:
            _NETO_CHAT_WINDOW = None
            self.chat.destroy()
        except Exception:
            pass

    def odakla(self, acilis_mesaji: str | None = None):
        try:
            self.chat.deiconify()
        except Exception:
            pass
        try:
            self.chat.lift()
            _focus_safe(self.chat, force=True)
        except Exception:
            pass
        if acilis_mesaji:
            self._mesaj_yaz("system", acilis_mesaji, kaydet=True)
            self._durum_yaz(acilis_mesaji, "#ffcc66")

    def model_degistir(self, secim):
        self.aktif_model = secim

        try:
            neto_ai.aktif_modeli_ayarla(secim)
        except Exception:
            pass

        if secim == "NetOps Agent K2":
            self.status_label.configure(text="K2", text_color="#00ffaa")
        else:
            self.status_label.configure(text="K1", text_color="#7ddc7d")

        try:
            self._mesaj_yaz("system", (_chat_text("chat_model_k2_enabled") if secim == "NetOps Agent K2" else _chat_text("chat_model_k1_enabled")))
        except Exception:
            pass

    def ai_kurulum_baslat(self):
        """Web tabanlı cevap modunu gösterir; ek kurulum istemez."""
        try:
            self._mesaj_yaz(
                "system",
                "Web tabanlı cevap motoru hazır. Mesajını yazabilirsin.",
            )
            self._durum_yaz(_chat_text("chat_install_ai"), "#7ddc7d")
            _focus_safe(self.msg_entry)

        except Exception as e:
            self._mesaj_yaz("system", _chat_text("chat_error", error=e))
            self._durum_yaz(T("error"), "#ff6666")

    def _icon_ayarla(self):
        logo_path = resource_path("NetoAsistan.ico")
        if not os.path.exists(logo_path):
            logo_path = resource_path("Logo.ico")

        if os.path.exists(logo_path):
            try:
                self.chat.iconbitmap(logo_path)
            except Exception:
                pass

    def _arayuz_olustur(self):

        # =========================
        # HEADER
        # =========================
        self.header = ctk.CTkFrame(
            self.chat,
            fg_color=self._theme["header"],
            corner_radius=0
        )
        self.header.pack(fill="x")

        logo_frame = ctk.CTkFrame(
            self.header,
            fg_color="transparent"
        )
        logo_frame.pack(side="left", padx=18, pady=10)

        # =========================
        # PNG LOGO
        # =========================
        logo_path_png = resource_path("NetoAsistan.png")
        if not os.path.exists(logo_path_png):
            logo_path_png = resource_path("Logo.png")

        if os.path.exists(logo_path_png):

            try:
                self.logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path_png),
                    dark_image=Image.open(logo_path_png),
                    size=(30, 30)
                )

                logo_label = ctk.CTkLabel(
                    logo_frame,
                    image=self.logo_image,
                    text=""
                )

                logo_label.pack(side="left", padx=(0, 10))

            except Exception:
                pass

        # =========================
        # BAŞLIK
        # =========================
        title_label = ctk.CTkLabel(
            logo_frame,
            text=f"{_chat_text('chat_title')} · v1.37",
            font=("Segoe UI", 20, "bold"),
            text_color="#ffffff"
        )

        title_label.pack(side="left")

        # =========================
        # DURUM
        # =========================
        self.status_label = ctk.CTkLabel(
            self.header,
            text=T("ready"),
            font=("Segoe UI", 12),
            text_color="#7ddc7d"
        )

        self.status_label.pack(side="right", padx=18)

        # =========================
        # MODEL SEÇİCİ
        # =========================
        self.aktif_model = "NetOps Agent K1"

        self.model_secici = ctk.CTkOptionMenu(
            self.header,
            values=["NetOps Agent K1", "NetOps Agent K2"],
            width=130,
            command=self.model_degistir
        )

        self.model_secici.pack(side="right", padx=10)

        self.model_secici.set("NetOps Agent K1")

        self.ai_kur_button = ctk.CTkButton(
            self.header,
            text=_chat_text("chat_install_ai"),
            width=80,
            height=28,
            fg_color=self._theme["entry"],
            hover_color="#444444",
            text_color="#ffffff",
            command=self.ai_kurulum_baslat
        )

        self.ai_kur_button.pack(side="right", padx=8)

        self.clear_history_button = ctk.CTkButton(
            self.header,
            text="🗑",
            width=34,
            height=28,
            fg_color=self._theme["entry"],
            hover_color="#444444",
            text_color="#ffffff",
            command=self.sohbet_gecmisini_temizle,
        )
        self.clear_history_button.pack(side="right", padx=(0, 8))

        # =========================
        # CHAT
        # =========================
        self.chat_history = ctk.CTkTextbox(
            self.chat,
            font=("Segoe UI", 13),
            fg_color=self._theme["card"],
            text_color="#e0e0e0",
            border_width=1,
            border_color=self._theme["border"],
            wrap="word",
            state="disabled"
        )

        self.chat_history.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )

        # =========================
        # ALT BAR
        # =========================
        self.input_frame = ctk.CTkFrame(
            self.chat,
            fg_color=self._theme["header"],
            corner_radius=12
        )

        self.input_frame.pack(
            fill="x",
            padx=15,
            pady=(0, 15)
        )

        # =========================
        # GİRİŞ
        # =========================
        self.msg_entry = ctk.CTkEntry(
            self.input_frame,
            font=("Segoe UI", 14),
            fg_color=self._theme["entry"],
            text_color="#ffffff",
            border_width=1,
            border_color=self._theme["entry_border"],
            placeholder_text=_chat_text("chat_input_placeholder")
        )

        self.msg_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=12,
            pady=12
        )

        self.msg_entry.bind(
            "<Return>",
            lambda e: self.mesaj_gonder()
        )

        # =========================
        # GÖNDER
        # =========================
        self.send_button = ctk.CTkButton(
            self.input_frame,
            text=T("send"),
            font=("Segoe UI", 13, "bold"),
            fg_color=self._theme["button"],
            text_color="#ffffff",
            hover_color=self._theme["button_hover"],
            corner_radius=10,
            width=90,
            command=self.mesaj_gonder
        )

        self.send_button.pack(
            side="right",
            padx=(0, 12),
            pady=12
        )

        self.beta_label = ctk.CTkLabel(
            self.chat,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color=self._theme["accent"],
            anchor="w",
            justify="left"
        )

    def _sohbet_gecmisini_goster(self):
        if not self.chat.winfo_exists():
            return
        try:
            self.chat_history.configure(state="normal")
            self.chat_history.delete("1.0", "end")
            for item in self.chat_history_data.get("messages", []):
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", "system"))
                text = str(item.get("text", ""))
                if not text.strip():
                    continue
                if role == "user":
                    satir = f"\n👤 {_chat_text('chat_user')}: {text}\n"
                elif role == "ai":
                    satir = f"🤖 {_chat_text('chat_ai')}: {text}\n"
                else:
                    satir = f"⚙️ {_chat_text('chat_system')}: {text}\n"
                self.chat_history.insert("end", satir)
            self.chat_history.configure(state="disabled")
            self.chat_history.see("end")
        except Exception:
            try:
                self.chat_history.configure(state="disabled")
            except Exception:
                pass

    def _sohbet_gecmisini_ekle(self, kim: str, mesaj: str):
        if not mesaj:
            return
        if kim not in {"user", "ai", "system"}:
            kim = "system"
        self.chat_history_data.setdefault("messages", [])
        self.chat_history_data["messages"].append(
            {
                "role": kim,
                "text": str(mesaj),
                "ts": time.time(),
            }
        )
        self.chat_history_data["messages"] = list(self.chat_history_data["messages"])[-CHAT_HISTORY_LIMIT:]
        _chat_history_kaydet(self.chat_history_data)

    def sohbet_gecmisini_temizle(self):
        try:
            self.chat_history_data = _chat_history_varsayilan()
            _chat_history_kaydet(self.chat_history_data)
            self._sohbet_gecmisini_goster()
            self._mesaj_yaz("system", "Sohbet geçmişi temizlendi.", kaydet=False)
            self._durum_yaz("Sohbet geçmişi temizlendi.", "#7ddc7d")
        except Exception as e:
            self._mesaj_yaz("system", _chat_text("chat_error", error=e), kaydet=False)

    def _show_beta_banner(self) -> None:
        if self.beta_label is None:
            return
        try:
            self.beta_label.configure(
                text=f"{_chat_text('chat_beta_note')} · v1.37",
                text_color=self._agent_theme["accent"],
            )
            if not self.beta_label.winfo_ismapped():
                self.beta_label.pack(fill="x", padx=18, pady=(0, 10))
        except Exception:
            pass

    def _apply_agent_theme(self, ratio: float) -> None:
        if not self.chat.winfo_exists():
            return
        ratio = max(0.0, min(1.0, float(ratio)))
        try:
            self.chat.configure(
                fg_color=_mix_color(self._theme["window"], self._agent_theme["window"], ratio)
            )
            if self.header is not None:
                self.header.configure(
                    fg_color=_mix_color(self._theme["header"], self._agent_theme["header"], ratio)
                )
            if self.input_frame is not None:
                self.input_frame.configure(
                    fg_color=_mix_color(self._theme["header"], self._agent_theme["header"], ratio)
                )
            self.chat_history.configure(
                fg_color=_mix_color(self._theme["card"], self._agent_theme["card"], ratio),
                border_color=_mix_color(self._theme["border"], self._agent_theme["border"], ratio),
            )
            self.msg_entry.configure(
                fg_color=_mix_color(self._theme["entry"], self._agent_theme["entry"], ratio),
                border_color=_mix_color(self._theme["entry_border"], self._agent_theme["entry_border"], ratio),
            )
            self.send_button.configure(
                fg_color=_mix_color(self._theme["button"], self._agent_theme["button"], ratio),
                hover_color=_mix_color(self._theme["button_hover"], self._agent_theme["button_hover"], ratio),
            )
            if hasattr(self, "clear_history_button") and self.clear_history_button.winfo_exists():
                self.clear_history_button.configure(
                    fg_color=_mix_color(self._theme["entry"], self._agent_theme["entry"], ratio),
                    hover_color=_mix_color("#444444", self._agent_theme["button_hover"], ratio),
                )
            if self.beta_label is not None and self.beta_label.winfo_exists():
                self.beta_label.configure(
                    text_color=_mix_color(self._theme["accent"], self._agent_theme["accent"], ratio),
                )
        except Exception:
            pass

    def _flash_agent_theme(self) -> None:
        if self.agent_flash_job is not None:
            try:
                self.chat.after_cancel(self.agent_flash_job)
            except Exception:
                pass
        steps = [0.0, 0.18, 0.4, 0.68, 1.0, 0.7, 0.42, 0.15, 0.0]
        delay = 42

        def tick(index: int) -> None:
            if not self.chat.winfo_exists():
                return
            if index >= len(steps):
                self.agent_flash_job = None
                self._apply_agent_theme(0.0)
                return
            self._apply_agent_theme(steps[index])
            self.agent_flash_job = self.chat.after(delay, lambda: tick(index + 1))

        tick(0)

    def _handle_agent_trigger(self, app_name: str | None = None) -> None:
        self.agent_mode = True
        self._show_beta_banner()
        self._flash_agent_theme()
        self._durum_yaz(_chat_text("chat_agent_prompt"), self._agent_theme["accent"])
        self._mesaj_yaz("system", _chat_text("chat_agent_prompt"))
        self.msg_entry.configure(placeholder_text=_chat_text("chat_agent_placeholder"))
        _focus_safe(self.msg_entry)
        sound_path = _first_existing_path("neto_startup_sound.mp3", "denielcz-done-463074.mp3")
        _play_sound_async(sound_path)
        if app_name:
            self._mesaj_yaz("user", app_name)
            self._buton_kilit(True)
            threading.Thread(
                target=self._ai_thread,
                args=(app_name, True),
                daemon=True,
                name="NetoChatAgentAI",
            ).start()
        return

    def _durum_yaz(self, text, renk="#7ddc7d"):

        if self.chat.winfo_exists():
            self.status_label.configure(
                text=text,
                text_color=renk
            )

    def _mesaj_yaz(self, kim, mesaj, kaydet: bool = True):

        if not self.chat.winfo_exists():
            return

        self.chat_history.configure(state="normal")

        if kim == "user":
            self.chat_history.insert(
                "end",
                f"\n👤 {_chat_text('chat_user')}: {mesaj}\n"
            )

        elif kim == "ai":
            self.chat_history.insert(
                "end",
                f"🤖 {_chat_text('chat_ai')}: {mesaj}\n"
            )

        else:
            self.chat_history.insert(
                "end",
                f"⚙️ {_chat_text('chat_system')}: {mesaj}\n"
            )

        self.chat_history.configure(state="disabled")
        self.chat_history.see("end")

        if kaydet:
            self._sohbet_gecmisini_ekle(kim, mesaj)

    def _buton_kilit(self, kilitli):

        self.waiting = kilitli

        if kilitli:

            self.send_button.configure(
                state="disabled",
                text=T("send")
            )

            self.msg_entry.configure(state="disabled")

        else:

            self.send_button.configure(
                state="normal",
                text=T("send")
            )

            self.msg_entry.configure(state="normal")
            self.msg_entry.configure(placeholder_text=_chat_text("chat_input_placeholder"))

            self._durum_yaz(
                T("ready"),
                "#7ddc7d"
            )

            _focus_safe(self.msg_entry)

    def mesaj_gonder(self):

        if self.waiting:
            return

        mesaj = self.msg_entry.get().strip()

        if not mesaj:
            return

        self.msg_entry.delete(0, "end")

        if mesaj.casefold() == ".agent":
            self._handle_agent_trigger()
            return

        if mesaj.casefold() == "n.ext":
            self.agent_mode = False
            self._show_beta_banner()
            self._mesaj_yaz("system", "Agent kapatıldı.")
            self._durum_yaz("Agent kapatıldı.", "#7ddc7d")
            self.msg_entry.configure(placeholder_text=_chat_text("chat_input_placeholder"))
            _focus_safe(self.msg_entry)
            return

        if self.agent_mode:
            self._mesaj_yaz("user", mesaj)
            self._buton_kilit(True)
            thread = threading.Thread(
                target=self._ai_thread,
                args=(mesaj, True),
                daemon=True,
            )
            thread.start()
            return

        self._mesaj_yaz(
            "user",
            mesaj
        )

        self._buton_kilit(True)

        thread = threading.Thread(
            target=self._ai_thread,
            args=(mesaj, False),
            daemon=True
        )

        thread.start()

    def _ai_thread(self, mesaj, agent_modu=False):

        try:
            cevap = neto_ai_cevap_ver(mesaj, agent_modu=agent_modu)

        except Exception as e:
            cevap = _chat_text("chat_error", error=e)

        self.chat.after(
            0,
            lambda: self._cevabi_isle(mesaj, cevap)
        )

    def _cevabi_isle(self, mesaj, cevap):

        try:

            if not cevap:
                cevap = T("chat_no_answer")

            if self.agent_mode and self._ozel_komut_mu(cevap):
                self._mesaj_yaz("ai", _chat_text("chat_agent_error", error="Agent modunda komut yürütmem."))
            elif self._ozel_komut_mu(cevap):

                sonuc = self._ana_asistana_gonder(cevap)

                if sonuc:
                    self._mesaj_yaz("ai", sonuc)

                else:
                    self._mesaj_yaz("ai", cevap)

            else:
                self._mesaj_yaz("ai", cevap)

        except Exception as e:

            self._mesaj_yaz(
                "system",
                _chat_text("chat_error", error=e)
            )

        finally:
            self._buton_kilit(False)

    def _ozel_komut_mu(self, cevap):

        return (
            cevap.startswith("__SES__:") or
            cevap.startswith("__KOMUT__:") or
            cevap.startswith("__HESAPLA__:") or
            cevap.startswith("__HAVA__:")
        )

    def _ana_asistana_gonder(self, komut):

        try:
            import __main__ as ana_mod

            if hasattr(ana_mod, "lokal_sistem_islemcisi"):

                return ana_mod.lokal_sistem_islemcisi(komut)

            return T("chat_no_answer")

        except Exception as e:

            return _chat_text("chat_error", error=e)


def neto_chat_ac(root, acilis_mesaji: str | None = None):
    global _NETO_CHAT_WINDOW

    if _NETO_CHAT_WINDOW is not None:
        try:
            if _NETO_CHAT_WINDOW.chat.winfo_exists():
                _NETO_CHAT_WINDOW.odakla(acilis_mesaji=acilis_mesaji)
                return _NETO_CHAT_WINDOW
        except Exception:
            _NETO_CHAT_WINDOW = None

    return NetoChatWindow(root, acilis_mesaji=acilis_mesaji)
