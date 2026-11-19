"""NetOps Remote surface.

This is the focused companion window for the Termux bridge.  It deliberately
exposes only paired-device operations and the allowlisted input protocol; it
does not execute arbitrary shell text on the phone or on the PC.
"""
from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk


REMOTE_GIF_NAME = "Remote.gif"
REMOTE_TITLE = "NetOps Remote"
REMOTE_BLUE = "#3b82f6"
REMOTE_BLUE_HOVER = "#2563eb"
REMOTE_BG = "#0b0e13"
REMOTE_PANEL = "#121720"
REMOTE_CARD = "#171d27"
REMOTE_BORDER = "#2a3445"
REMOTE_TEXT = "#eef3fb"
REMOTE_MUTED = "#94a3b8"


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _asset_path() -> Path:
    bundled = _project_root() / "assets" / REMOTE_GIF_NAME
    if bundled.is_file():
        return bundled
    return _project_root() / REMOTE_GIF_NAME


def remote_command_catalog() -> tuple[tuple[str, str], ...]:
    """Return the only phone commands exposed by this surface."""
    return (
        ("Durumu yenile", "request_status"),
        ("Şimdi çalanı getir", "request_media"),
        ("Ses aç", "volume_up"),
        ("Ses kıs", "volume_down"),
        ("Sesi kapat", "volume_mute"),
    )


def _safe_error(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("error") or result.get("message") or "İşlem tamamlanamadı.")
    return str(result or "İşlem tamamlanamadı.")


def _remote_input_request(key: str, modifiers: Any = None, device_id: str = "") -> Any:
    """Adapt the hub callback shape to the allowlisted PC input handler."""
    from neto_remote_pc_actions import handle_remote_input

    return handle_remote_input(key, modifiers)


class _GifView(tk.Label):
    """Small optional animated GIF view with a static fallback."""

    def __init__(self, master: Any, path: Path, size: int = 88) -> None:
        super().__init__(master, bg=REMOTE_PANEL, bd=0, highlightthickness=0)
        self._frames: list[Any] = []
        self._index = 0
        self._size = size
        try:
            from PIL import Image, ImageSequence, ImageTk

            image = Image.open(path)
            for frame in ImageSequence.Iterator(image):
                frame = frame.convert("RGBA")
                frame.thumbnail((size, size), Image.Resampling.LANCZOS)
                self._frames.append(ImageTk.PhotoImage(frame))
        except Exception:
            try:
                self._frames = [tk.PhotoImage(file=str(path))]
            except Exception:
                self._frames = []
        if self._frames:
            self.configure(image=self._frames[0], width=size, height=size)
            self._animate()
        else:
            self.configure(width=size, height=size)

    def _animate(self) -> None:
        if not self.winfo_exists() or not self._frames:
            return
        self.configure(image=self._frames[self._index])
        self._index = (self._index + 1) % len(self._frames)
        self.after(90, self._animate)


class RemoteSurface:
    def __init__(self, root: ctk.CTk, close_callback: Callable[[], None] | None = None) -> None:
        self.root = root
        self.close_callback = close_callback
        self._selected_device = ""
        self._device_rows: dict[str, ctk.CTkFrame] = {}
        self._busy = False
        self._status_text = tk.StringVar(value="Remote köprüsü hazırlanıyor...")
        self._pair_text = tk.StringVar(value="------")
        self._endpoint_text = tk.StringVar(value="ws://127.0.0.1:8765")
        self._device_text = tk.StringVar(value="Cihaz seçilmedi")
        self._build()
        self._start_services()
        self.root.after(150, self.refresh)
        self.root.after(1200, self._periodic_refresh)

    def _build(self) -> None:
        self.root.title(REMOTE_TITLE)
        self.root.geometry("980x650")
        self.root.minsize(860, 560)
        self.root.configure(fg_color=REMOTE_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ctk.CTkFrame(self.root, fg_color=REMOTE_BG, corner_radius=0)
        outer.pack(fill="both", expand=True)

        rail = ctk.CTkFrame(outer, width=235, fg_color=REMOTE_PANEL, corner_radius=0)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(20, 12))
        logo_path = _asset_path()
        if logo_path.is_file():
            _GifView(brand, logo_path, size=54).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(brand, text="NETOPS\nREMOTE", justify="left", anchor="w",
                     font=("Segoe UI Semibold", 18), text_color=REMOTE_TEXT).pack(side="left")
        ctk.CTkLabel(rail, text="Termux cihaz köprüsü", anchor="w",
                     font=("Segoe UI", 11), text_color=REMOTE_MUTED).pack(fill="x", padx=18, pady=(0, 20))

        self._rail_button(rail, "Bağlantı", self.refresh, active=True)
        self._rail_button(rail, "Termux kurulumu", self.install_termux)
        self._rail_button(rail, "Termux'u bağla", self.connect_termux)
        self._rail_button(rail, "Klavye kontrolü", self.open_control_help)
        self._rail_button(rail, "Günlükler", self.open_logs)
        ctk.CTkFrame(rail, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkButton(rail, text="NetOps'a dön", height=38, corner_radius=10,
                      fg_color=REMOTE_CARD, hover_color=REMOTE_BORDER, text_color=REMOTE_TEXT,
                      command=self.close).pack(fill="x", padx=16, pady=16)

        content = ctk.CTkFrame(outer, fg_color=REMOTE_BG, corner_radius=0)
        content.pack(side="left", fill="both", expand=True, padx=20, pady=18)
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(header, text="Remote çalışma alanı", font=("Segoe UI Semibold", 24),
                     text_color=REMOTE_TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(header, textvariable=self._status_text, font=("Segoe UI", 11),
                     text_color=REMOTE_MUTED, anchor="e").pack(side="right", padx=8)

        connection = ctk.CTkFrame(content, fg_color=REMOTE_CARD, border_width=1,
                                  border_color=REMOTE_BORDER, corner_radius=14)
        connection.pack(fill="x", pady=(0, 14))
        left = ctk.CTkFrame(connection, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=16, pady=14)
        ctk.CTkLabel(left, text="Termux bağlantı noktası", text_color=REMOTE_MUTED,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x")
        ctk.CTkLabel(left, textvariable=self._endpoint_text, text_color=REMOTE_TEXT,
                     font=("Consolas", 12), anchor="w").pack(fill="x", pady=(3, 0))
        right = ctk.CTkFrame(connection, fg_color="transparent")
        right.pack(side="right", padx=16, pady=10)
        ctk.CTkLabel(right, text="Eşleştirme kodu", text_color=REMOTE_MUTED,
                     font=("Segoe UI", 10)).pack()
        ctk.CTkLabel(right, textvariable=self._pair_text, text_color=REMOTE_BLUE,
                     font=("Consolas", 20, "bold")).pack()

        self.devices_frame = ctk.CTkScrollableFrame(content, fg_color="transparent",
                                                      label_text="BAĞLI TERMUX CİHAZLARI",
                                                      label_text_color=REMOTE_MUTED)
        self.devices_frame.pack(fill="both", expand=True)

        chat = ctk.CTkFrame(content, fg_color=REMOTE_CARD, border_width=1,
                           border_color=REMOTE_BORDER, corner_radius=14)
        chat.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(chat, text="Termux sohbeti", text_color=REMOTE_MUTED,
                     font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", padx=14, pady=(10, 2))
        self.chat_box = ctk.CTkTextbox(chat, height=62, fg_color=REMOTE_BG,
                                       border_width=0, text_color=REMOTE_TEXT,
                                       font=("Segoe UI", 11), wrap="word")
        self.chat_box.pack(fill="x", padx=10, pady=(0, 8))
        self.chat_box.insert("end", "NetOps: Termux'a bağlandığınızda burada konuşabilirsiniz.\n")
        self.chat_box.configure(state="disabled")
        chat_entry = ctk.CTkFrame(chat, fg_color="transparent")
        chat_entry.pack(fill="x", padx=10, pady=(0, 10))
        self.chat_input = ctk.CTkEntry(chat_entry, height=34, corner_radius=9,
                                       placeholder_text="Termux'a bir şey sor...")
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", lambda _event: self.send_chat())
        ctk.CTkButton(chat_entry, text="Gönder", width=88, height=34, corner_radius=9,
                      fg_color=REMOTE_BLUE, hover_color=REMOTE_BLUE_HOVER,
                      command=self.send_chat).pack(side="right")

        action = ctk.CTkFrame(content, fg_color=REMOTE_CARD, border_width=1,
                              border_color=REMOTE_BORDER, corner_radius=14)
        action.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(action, textvariable=self._device_text, text_color=REMOTE_TEXT,
                     font=("Segoe UI Semibold", 13), anchor="w").pack(side="left", padx=16, pady=14)
        ctk.CTkButton(action, text="Durum", width=92, height=34, corner_radius=9,
                      fg_color=REMOTE_BLUE, hover_color=REMOTE_BLUE_HOVER,
                      command=lambda: self.send_command("request_status")).pack(side="right", padx=(4, 10), pady=10)
        ctk.CTkButton(action, text="Şimdi çalan", width=110, height=34, corner_radius=9,
                      fg_color=REMOTE_CARD, hover_color=REMOTE_BORDER, text_color=REMOTE_TEXT,
                      command=lambda: self.send_command("request_media")).pack(side="right", padx=4, pady=10)

    def _rail_button(self, parent: Any, text: str, command: Callable[[], None], active: bool = False) -> None:
        ctk.CTkButton(parent, text=text, anchor="w", height=38, corner_radius=9,
                      fg_color=REMOTE_BLUE if active else "transparent",
                      hover_color=REMOTE_BLUE_HOVER if active else REMOTE_CARD,
                      text_color=REMOTE_TEXT, command=command).pack(fill="x", padx=12, pady=4)

    def _start_services(self) -> None:
        try:
            import neto_device_hub

            neto_device_hub.device_hub_set_input_handler(_remote_input_request)
            neto_device_hub.device_hub_set_assistant_handler(None)
            neto_device_hub.device_hub_set_media_handler(None)
            result = neto_device_hub.device_hub_start(host="0.0.0.0", port=8765)
            if not result.get("ok") and "already" not in str(result.get("error", "")).lower():
                self._status_text.set("Köprü başlatılamadı")
            self._pair_text.set(neto_device_hub.device_hub_create_pairing_code())
        except Exception as exc:
            self._status_text.set(f"Köprü hatası: {exc}")

    def _periodic_refresh(self) -> None:
        if self.root.winfo_exists():
            self.refresh()
            self.root.after(1200, self._periodic_refresh)

    def refresh(self) -> None:
        try:
            import neto_device_hub

            snapshot = neto_device_hub.device_hub_snapshot()
            self._pair_text.set(neto_device_hub.device_hub_create_pairing_code())
            devices = snapshot.get("devices") or []
            for child in self.devices_frame.winfo_children():
                child.destroy()
            self._device_rows.clear()
            if not devices:
                ctk.CTkLabel(self.devices_frame, text="Henüz eşleştirilmiş cihaz yok. Termux kurulumu ile başlayın.",
                             text_color=REMOTE_MUTED, anchor="w").pack(fill="x", padx=8, pady=18)
                self._status_text.set("Cihaz bekleniyor")
                return
            for device in devices:
                self._render_device(device)
            self._status_text.set(f"{len(devices)} cihaz kayıtlı")
        except Exception as exc:
            self._status_text.set(f"Yenileme hatası: {exc}")

    def _render_device(self, device: dict[str, Any]) -> None:
        device_id = str(device.get("device_id") or "")
        online = bool(device.get("online"))
        title = str(device.get("alias") or device.get("device_name") or device_id or "Bilinmeyen cihaz")
        card = ctk.CTkFrame(self.devices_frame, fg_color=REMOTE_CARD, border_width=1,
                            border_color=REMOTE_BLUE if online else REMOTE_BORDER, corner_radius=12)
        card.pack(fill="x", padx=4, pady=5)
        text = ctk.CTkFrame(card, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        ctk.CTkLabel(text, text=("● " if online else "○ ") + title, text_color=REMOTE_TEXT,
                     font=("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        detail = f"{device.get('model') or 'Termux'} · {'çevrimiçi' if online else 'çevrimdışı'}"
        ctk.CTkLabel(text, text=detail, text_color=REMOTE_MUTED, font=("Segoe UI", 10),
                     anchor="w").pack(fill="x", pady=(2, 0))
        ctk.CTkButton(card, text="Seç", width=70, height=30, corner_radius=8,
                      fg_color=REMOTE_BLUE if device_id == self._selected_device else REMOTE_PANEL,
                      hover_color=REMOTE_BLUE_HOVER, command=lambda d=device_id: self.select_device(d)).pack(side="right", padx=12, pady=12)
        self._device_rows[device_id] = card
        if not self._selected_device and online:
            self.select_device(device_id)

    def select_device(self, device_id: str) -> None:
        self._selected_device = device_id
        self._device_text.set(f"Seçili cihaz: {device_id or 'yok'}")
        self.refresh()

    def _selected(self) -> str:
        if self._selected_device:
            return self._selected_device
        try:
            import neto_device_hub

            devices = neto_device_hub.device_hub_snapshot().get("devices") or []
            online = next((d for d in devices if d.get("online")), None)
            if online:
                self._selected_device = str(online.get("device_id") or "")
        except Exception:
            pass
        return self._selected_device

    def _append_chat(self, speaker: str, message: str) -> None:
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{speaker}: {message}\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def send_chat(self) -> None:
        text = self.chat_input.get().strip()
        if not text:
            return
        self.chat_input.delete(0, "end")
        self._append_chat("Sen", text)
        self.send_command("assistant_request", {"text": text}, output_chat=True)

    def send_command(self, command: str, args: dict[str, Any] | None = None, *, output_chat: bool = False) -> None:
        device_id = self._selected()
        if not device_id:
            self._status_text.set("Önce çevrimiçi bir cihaz seçin")
            return
        if self._busy:
            return
        self._busy = True

        def worker() -> None:
            try:
                import neto_device_hub

                result = neto_device_hub.device_hub_send_command(device_id, command, args or {}, timeout=8)
                message = result.get("display_text") or result.get("message") or result.get("result") or _safe_error(result)
                if output_chat:
                    self.root.after(0, lambda: self._append_chat("Termux", str(message)))
                else:
                    self.root.after(0, lambda: self._status_text.set(str(message)[:100]))
            except Exception as exc:
                self.root.after(0, lambda: self._status_text.set(f"Komut hatası: {exc}"))
            finally:
                self.root.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=worker, name="NetOpsRemoteCommand", daemon=True).start()

    def install_termux(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._status_text.set("USB cihazı ve Termux kontrol ediliyor...")

        def worker() -> None:
            try:
                import neto_android_device

                listed = neto_android_device.list_usb_devices()
                devices = [d for d in listed.get("usb_devices") or [] if d.get("state") == "device"]
                if not devices:
                    message = "Yetkili USB cihaz bulunamadı. USB hata ayıklamayı onaylayın."
                else:
                    serial = str(devices[0].get("serial") or "")
                    result = neto_android_device.install_termux_shell(serial)
                    message = result.get("message") if result.get("ok") else _safe_error(result)
                self.root.after(0, lambda: self._status_text.set(str(message)[:100]))
            except Exception as exc:
                self.root.after(0, lambda: self._status_text.set(f"Termux hatası: {exc}"))
            finally:
                self.root.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=worker, name="NetOpsTermuxInstall", daemon=True).start()

    def connect_termux(self) -> None:
        """Pair the first explicitly authorized USB device through Termux."""
        if self._busy:
            return
        self._busy = True
        self._status_text.set("Termux ajanı USB üzerinden bağlanıyor...")

        def worker() -> None:
            try:
                import neto_android_device
                import neto_device_hub

                listed = neto_android_device.list_usb_devices()
                devices = [d for d in listed.get("usb_devices") or [] if d.get("state") == "device"]
                if not devices:
                    message = "Yetkili USB cihaz bulunamadı. USB hata ayıklama iznini onaylayın."
                else:
                    serial = str(devices[0].get("serial") or "")
                    pairing = neto_device_hub.device_hub_create_pairing_code()
                    result = neto_android_device.register_termux_device(
                        serial,
                        "ws://127.0.0.1:8765",
                        pairing,
                        "Telefonum",
                    )
                    message = result.get("message") if result.get("ok") else _safe_error(result)
                self.root.after(0, lambda: self._status_text.set(str(message)[:100]))
                self.root.after(0, self.refresh)
            except Exception as exc:
                self.root.after(0, lambda: self._status_text.set(f"Bağlantı hatası: {exc}"))
            finally:
                self.root.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=worker, name="NetOpsTermuxPair", daemon=True).start()

    def open_control_help(self) -> None:
        self._status_text.set("Termux: netops control | ok tuşu çıkar | c/e/f/v uygulama kısayolu")

    def open_logs(self) -> None:
        path = _project_root() / "logs" / "device_hub.log"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path.parent))
            self._status_text.set("Remote günlük klasörü açıldı")
        except Exception as exc:
            self._status_text.set(f"Günlük açılamadı: {exc}")

    def close(self) -> None:
        try:
            self.root.destroy()
        finally:
            if self.close_callback:
                self.close_callback()


def open_remote_surface(close_callback: Callable[[], None] | None = None) -> RemoteSurface:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    surface = RemoteSurface(root, close_callback=close_callback)
    root.mainloop()
    return surface


def run() -> int:
    open_remote_surface()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
