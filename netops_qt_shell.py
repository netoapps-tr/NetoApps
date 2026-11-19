"""Native Qt Widgets presentation for NetOps.

This module intentionally uses stock PySide6 widgets and no QSS theme layer.
The backend is injected so the UI can be tested without starting NetOps
services or a second application event loop.
"""

from __future__ import annotations

import os
import math
import json
from queue import Empty, Queue
import threading
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QTimer, Qt, Property, Signal, QSize
from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QImage, QImageReader, QMovie, QPainter, QPainterPath, QPixmap

from netops_qt_backend import QtBackend, build_qt_backend
from netops_icon_pack import icon as netops_icon


_PAGES = (
    ("chat", "Sohbet"),
    ("devices", "Cihazlar"),
    ("now_playing", "Now Playing"),
    ("automations", "Otomasyonlar"),
    ("remote", "Remote"),
    ("system", "Sistem Durumu"),
    ("notifications", "Bildirimler"),
    ("settings", "Ayarlar"),
)


def native_legacy_layout_contract() -> dict[str, tuple[str, ...] | str]:
    """Describe the preserved legacy NetOps layout in stable UI terms."""
    return {
        "top_status": ("SİSTEM", "REMOTE", "BİLDİRİMLER", "NOW PLAYING"),
        "sidebar": (
            "Genel Bakış",
            "Cihazlar",
            "Now Playing",
            "Otomasyonlar",
            "Remote",
            "Ayarlar",
        ),
        "bottom_input": "Mesajını yaz...",
    }


def native_page_keys() -> tuple[str, ...]:
    return tuple(key for key, _label in _PAGES)


def native_motion_contract() -> dict[str, int | str]:
    return {"startup_ms": 220, "page_ms": 180, "property": "windowOpacity"}


def native_animation_contract() -> dict[str, int]:
    return {
        "logo_fade_ms": 260,
        "sidebar_stagger_ms": 35,
        "button_feedback_ms": 120,
    }


def native_brand_contract() -> dict[str, str]:
    return {
        "app_name": "NetOps",
        "version": "1.53.1",
        "window_title": "NetOps 1.53.1",
        "logo_file": "Logo.png",
    }


def native_command_bar_contract() -> dict[str, tuple[str, ...] | int]:
    return {
        "navigation": ("Geri", "İleri", "Görünüm"),
        "menus": ("Dosya", "Düzenle", "Görünüm", "Yardım"),
        "overflow": "...",
        "height_px": 36,
    }


def native_help_center_contract() -> dict[str, str]:
    return {
        "name": "OpsCenter",
        "url": "https://sites.google.com/view/nqdestek/opscenter",
        "instruction": "Opscenter'a Gitmek için başka cihaz ile okutun.",
    }


def native_visual_contract() -> dict[str, int]:
    return {
        "now_playing_poll_ms": 1000,
        "system_poll_ms": 1000,
        "button_radius_px": 10,
        "button_feedback_ms": 120,
    }


def native_window_contract() -> dict[str, bool]:
    return {"start_maximized": True}


def native_settings_sections() -> tuple[str, ...]:
    return (
        "Genel",
        "Sistem",
        "Görünüm",
        "Pencere Yöneticisi",
        "Netolab",
        "Güvenlik",
        "Güncellemeler",
        "Hakkında",
    )


def native_sidebar_contract() -> dict[str, int | str]:
    return {
        "settings_button_count": 1,
        "panel_radius_px": 16,
        "status_message": "",
        "settings_position": "bottom",
    }


def native_sidebar_extension_contract() -> dict[str, tuple[str, ...] | str]:
    return {
        "sections": ("YAKIN ZAMANLAR",),
        "quick_actions": (),
        "plan_action": "＋  Yeni sohbet",
    }


def native_sidebar_chat_contract() -> dict[str, tuple[str, ...] | str | int]:
    return {
        "header": "Yakın zamanlar",
        "new_chat": "＋  Yeni sohbet",
        "max_items": 24,
        "settings_button_count": 1,
        "resource_metrics": ("cpu", "ram", "gpu"),
    }


def native_sidebar_motion_contract() -> dict[str, int]:
    return {
        "edge_trigger_px": 18,
        "open_ms": 220,
        "close_ms": 160,
        "poll_ms": 50,
    }


def native_settings_animation_contract() -> dict[str, int | float]:
    return {
        "surface_ms": 220,
        "tab_ms": 160,
        "start_opacity": 0.78,
    }


def native_sidebar_icon_contract() -> dict[str, str]:
    return {
        "chat": "message",
        "devices": "computer",
        "now_playing": "media",
        "automations": "workflow",
        "system": "system",
        "settings": "settings",
    }


def _remove_logo_background(pixmap: QPixmap) -> QPixmap:
    """Make only the border-connected black background transparent."""
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return pixmap

    def is_background(x: int, y: int) -> bool:
        color = image.pixelColor(x, y)
        return (
            color.alpha() > 0
            and color.red() <= 18
            and color.green() <= 18
            and color.blue() <= 18
        )

    pending: list[tuple[int, int]] = []
    for x in range(width):
        pending.append((x, 0))
        if height > 1:
            pending.append((x, height - 1))
    for y in range(1, height - 1):
        pending.append((0, y))
        if width > 1:
            pending.append((width - 1, y))

    visited: set[tuple[int, int]] = set()
    while pending:
        x, y = pending.pop()
        if (x, y) in visited or not is_background(x, y):
            continue
        visited.add((x, y))
        color = image.pixelColor(x, y)
        color.setAlpha(0)
        image.setPixelColor(x, y, color)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                pending.append((nx, ny))

    return QPixmap.fromImage(image)


def load_cover_pixmap(path: str) -> QPixmap:
    """Load album art by file content, not by a possibly stale extension."""
    candidate = str(path or "").strip()
    if not candidate or not os.path.isfile(candidate):
        return QPixmap()
    try:
        reader = QImageReader(candidate)
        reader.setAutoTransform(True)
        image = reader.read()
        if not image.isNull():
            return QPixmap.fromImage(image)
    except Exception:
        pass
    return QPixmap(candidate)


def native_now_playing_contract() -> dict[str, int | str]:
    return {
        "fullscreen_title": "ŞU AN ÇALIYOR",
        "standby_title": "BEKLEME MODU",
        "refresh_ms": 1000,
    }


class ClickableFrame(QFrame):
    """Small clickable surface used for the compact Now Playing card."""

    clicked = Signal()
    doubleClicked = Signal()
    longPressed = Signal()
    mouseLeft = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(520)
        self._long_press_timer.timeout.connect(self._emit_long_press)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self.clicked.emit)
        self._long_press_triggered = False
        self._double_click_triggered = False

    def _emit_long_press(self) -> None:
        self._long_press_triggered = True
        self.longPressed.emit()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_triggered = False
            self._double_click_triggered = False
            self._long_press_timer.start()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_timer.stop()
            self._click_timer.stop()
            self._long_press_triggered = False
            self._double_click_triggered = True
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            was_long_press = self._long_press_triggered
            self._long_press_timer.stop()
            self._long_press_triggered = False
            if not was_long_press and not self._double_click_triggered:
                self._click_timer.start()
            self._double_click_triggered = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self.mouseLeft.emit()
        super().leaveEvent(event)


class ChatTypingIndicator(QFrame):
    """Small local GIF indicator shown while NetOps is preparing a reply."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatTypingBubble")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        self._label = QLabel(self)
        self._label.setObjectName("chatTypingLabel")
        movie_path = Path(__file__).with_name("assets") / "netops_typing.gif"
        self._movie = QMovie(str(movie_path), parent=self)
        if self._movie.isValid():
            self._movie.setScaledSize(QSize(42, 18))
            self._label.setMovie(self._movie)
            self._movie.start()
        else:
            self._label.setText("...")
        layout.addWidget(QLabel("NetOps", self))
        layout.addWidget(self._label)


class ChatTranscript(QScrollArea):
    """Scrollable WhatsApp-like conversation surface with aligned bubbles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatOutput")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._messages: list[dict[str, str]] = []
        self._message_rows: list[QWidget] = []
        self._surface = QWidget(self)
        self._surface.setObjectName("chatTranscriptSurface")
        self._layout = QVBoxLayout(self._surface)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)
        self._typing_row = QWidget(self._surface)
        typing_layout = QHBoxLayout(self._typing_row)
        typing_layout.setContentsMargins(0, 0, 0, 0)
        self._typing_indicator = ChatTypingIndicator(self._typing_row)
        typing_layout.addWidget(self._typing_indicator, 0, Qt.AlignmentFlag.AlignLeft)
        typing_layout.addStretch(1)
        self._layout.addWidget(self._typing_row)
        self._layout.addStretch(1)
        self._typing_row.hide()
        self.setWidget(self._surface)

    def setReadOnly(self, _read_only: bool) -> None:
        """Keep the old text-surface API used by the window setup."""

    def clear(self) -> None:
        for row in self._message_rows:
            row.deleteLater()
        self._message_rows.clear()
        self._messages.clear()
        self.hide_typing()

    def appendPlainText(self, text: str) -> None:
        for line in str(text).splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Sen:"):
                self.append_message(line[4:].strip(), "user")
            elif line.startswith("NetOps:"):
                self.append_message(line[7:].strip(), "assistant")
            else:
                self.append_message(line, "assistant")

    def append_message(self, text: str, role: str) -> None:
        text = str(text or "").strip()
        if not text:
            return
        role = "user" if role == "user" else "assistant"
        self._messages.append({"role": role, "text": text})

        row = QWidget(self._surface)
        row.setObjectName("chatMessageRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        bubble = QFrame(row)
        bubble.setObjectName("chatUserBubble" if role == "user" else "chatAssistantBubble")
        bubble.setMaximumWidth(540 if role == "user" else 820)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(3)
        if role == "assistant":
            sender = QLabel("NetOps", bubble)
            sender.setObjectName("chatBubbleSender")
            bubble_layout.addWidget(sender)
        body = QLabel(text, bubble)
        body.setObjectName("chatBubbleText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(body)
        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        else:
            row_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row_layout.addStretch(1)
        self._layout.insertWidget(self._layout.indexOf(self._typing_row), row)
        self._message_rows.append(row)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def toPlainText(self) -> str:
        return "\n\n".join(
            f"{'Sen' if message['role'] == 'user' else 'NetOps'}: {message['text']}"
            for message in self._messages
        )

    def show_typing(self) -> None:
        self._typing_row.show()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def hide_typing(self) -> None:
        self._typing_row.hide()

    def _scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class NowPlayingCover(QLabel):
    """Paint album art with a restrained circle-to-rounded-square reveal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._art = QPixmap()
        self._zoom = 0.62
        self._corner_radius = 32.0
        self._compact_circle = False
        self._reveal_animation: QParallelAnimationGroup | None = None
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _get_zoom(self) -> float:
        return self._zoom

    def _set_zoom(self, value: float) -> None:
        self._zoom = float(value)
        self.update()

    def _get_corner_radius(self) -> float:
        return self._corner_radius

    def _set_corner_radius(self, value: float) -> None:
        self._corner_radius = float(value)
        self.update()

    def _dispose_reveal_animation(self) -> None:
        animation = self._reveal_animation
        self._reveal_animation = None
        if animation is None:
            return
        try:
            animation.stop()
        except RuntimeError:
            # DeleteWhenStopped may already have released the Qt wrapper.
            return
        try:
            animation.deleteLater()
        except RuntimeError:
            pass

    def _clear_reveal_animation(self, animation: QParallelAnimationGroup) -> None:
        if self._reveal_animation is animation:
            self._reveal_animation = None

    zoom = Property(float, _get_zoom, _set_zoom)
    corner_radius = Property(float, _get_corner_radius, _set_corner_radius)

    def set_compact_circle(self, enabled: bool) -> None:
        self._compact_circle = bool(enabled)
        self._set_corner_radius(32.0 if self._compact_circle else 11.0)
        self.update()

    def set_art(self, pixmap: QPixmap, *, animate: bool = True) -> None:
        self._art = pixmap if not pixmap.isNull() else QPixmap()
        self.setText("")
        target_radius = 32.0 if self._compact_circle else 11.0
        if not animate or os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            self._set_zoom(1.0)
            self._set_corner_radius(target_radius)
            return
        self._dispose_reveal_animation()
        self._set_zoom(0.62)
        self._set_corner_radius(32.0)
        animation = QParallelAnimationGroup(self)
        animation.finished.connect(
            lambda animation=animation: self._clear_reveal_animation(animation)
        )
        zoom = QPropertyAnimation(self, b"zoom", animation)
        zoom.setDuration(220)
        zoom.setStartValue(0.62)
        zoom.setEndValue(1.0)
        zoom.setEasingCurve(QEasingCurve.Type.OutCubic)
        radius = QPropertyAnimation(self, b"corner_radius", animation)
        radius.setDuration(220)
        radius.setStartValue(32.0)
        radius.setEndValue(target_radius)
        radius.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.addAnimation(zoom)
        animation.addAnimation(radius)
        self._reveal_animation = animation
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def clear_art(self, text: str) -> None:
        self._art = QPixmap()
        self._set_zoom(1.0)
        self._set_corner_radius(32.0 if self._compact_circle else 11.0)
        self.setText(text)

    def paintEvent(self, event) -> None:
        if self._art.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#101521"))
        painter.drawRoundedRect(self.rect(), self._corner_radius, self._corner_radius)
        edge = min(self.width(), self.height()) * self._zoom
        rect = self.rect()
        art_rect = rect.adjusted(
            int((rect.width() - edge) / 2),
            int((rect.height() - edge) / 2),
            -int((rect.width() - edge) / 2),
            -int((rect.height() - edge) / 2),
        )
        path = QPainterPath()
        path.addRoundedRect(art_rect, min(self._corner_radius, edge / 2), min(self._corner_radius, edge / 2))
        painter.setClipPath(path)
        painter.drawPixmap(art_rect, self._art)


_NATIVE_ENGLISH_TRANSLATIONS: dict[str, str] = {
    "Geri": "Back",
    "İleri": "Forward",
    "Görünüm": "View",
    "Dosya": "File",
    "Düzenle": "Edit",
    "Yardım": "Help",
    "Yeni sohbet": "New chat",
    "Kapat": "Close",
    "Sohbeti temizle": "Clear chat",
    "Sohbeti kopyala": "Copy chat",
    "Now Playing'i aç/kapat": "Toggle Now Playing",
    "Kenar çubuğunu göster/gizle": "Show/hide sidebar",
    "Tam ekran görünümü": "Fullscreen view",
    "OpsCenter QR kodu": "OpsCenter QR code",
    "Ayarları aç": "Open settings",
    "NetOps hakkında": "About NetOps",
    "Sistem": "System",
    "Bildirimler": "Notifications",
    "QR kodu oluşturulamadı": "QR code could not be generated",
    "Opscenter'a Gitmek için başka cihaz ile okutun.": "Scan this with another device to open OpsCenter.",
    "NetOps: Yeni sohbet hazır.": "NetOps: New chat is ready.",
    "Hazır": "Ready",
    "SİSTEM": "SYSTEM",
    "BİLDİRİMLER": "NOTIFICATIONS",
    "Servis hatası": "Service error",
    "Ses": "Volume",
    "Müzik bekleniyor": "Waiting for music",
    "♪  Müzik bekleniyor": "♪  Waiting for music",
    "Ses: okunuyor": "Volume: reading",
    "Ses: okunamadı": "Volume: unavailable",
    "Ses: ayarlanamadı": "Volume: could not be set",
    "Sessize al": "Mute",
    "Sesi aç": "Unmute",
    "Sessiz": "Muted",
    "ÇALIŞMA ALANI": "WORKSPACE",
    "HIZLI EYLEMLER": "QUICK ACTIONS",
    "AI GÖREV PLANI": "AI TASK PLAN",
    "CİHAZ ÖZETİ": "DEVICE SUMMARY",
    "SON İŞLEMLER": "RECENT ACTIVITY",
    "＋  Komut konsolu": "＋  Command console",
    "＋  Yeni sohbet": "＋  New chat",
    "Yakın zamanlar": "Recent chats",
    "Henüz sohbet yok.": "No chats yet.",
    "Genel Bakış": "Overview",
    "Cihazlar": "Devices",
    "Otomasyonlar": "Automations",
    "SİSTEM DURUMU": "SYSTEM STATUS",
    "Ölçülüyor": "Measuring",
    "Kullanım": "Usage",
    "Ayarlar": "Settings",
    "Bildirimler": "Notifications",
    "Sistem taraması": "System scan",
    "Cihazları yenile": "Refresh devices",
    "Yeni sohbet": "New chat",
    "Görev oluştur": "Create task",
    "Çok adımlı komutlarını güvenli bir plan olarak hazırla.": "Turn multi-step commands into a safe plan.",
    "Onayla ile çalıştırılır": "Runs after confirmation",
    "Bağlı cihaz": "Connected devices",
    "Remote durumu": "Remote status",
    "Son işlem yok.": "No recent activity.",
    "AI görev planı hazır": "AI task planner ready",
    "Plan örneği hazırlandı": "A plan example is ready",
    "Örnek: RAM'i göster sonra müziği durdur": "Example: show RAM, then pause music",
    "Sistem Durumu": "System Status",
    "NetOps servisleri ve bilgisayar kaynakları.": "NetOps services and computer resources.",
    "Durum": "Status",
    "Durumu yenile": "Refresh status",
    "Cihazlar": "Devices",
    "Bağlı cihazları ve Remote durumunu izle.": "Monitor connected devices and Remote status.",
    "Cihaz": "Device",
    "Adres": "Address",
    "Cihazları yenile": "Refresh devices",
    "Çevrimiçi": "Online",
    "Çevrimdışı": "Offline",
    "Now Playing": "Now Playing",
    "Aktif medya oturumunu görüntüle.": "View the active media session.",
    "Kapak bekleniyor": "Waiting for cover art",
    "Şu an çalıyor": "Now playing",
    "Parça": "Track",
    "Sanatçı": "Artist",
    "Kaynak": "Source",
    "Kaynak bilgisi yok": "No source information",
    "Bekleniyor": "Waiting",
    "Önceki": "Previous",
    "Oynat / Duraklat": "Play / Pause",
    "Sonraki": "Next",
    "Bilgisayar ses seviyesi": "Computer volume",
    "Medya bilgisini yenile": "Refresh media info",
    "Tam ekran Now Playing": "Fullscreen Now Playing",
    "Otomasyonları yenile": "Refresh automations",
    "Zamanlayıcıları ve çalışma akışlarını görüntüle.": "View timers and workflows.",
    "Ad": "Name",
    "Aktif": "Active",
    "Tetikleyici": "Trigger",
    "Evet": "Yes",
    "Hayır": "No",
    "Bağlı telefon ve Termux cihazlarına güvenli komut gönder.": "Send secure commands to connected phones and Termux devices.",
    "Remote sonuçları burada görünecek.": "Remote results will appear here.",
    "Örnek: telefondaki durumu söyle": "Example: tell me the phone status",
    "Gönder": "Send",
    "Cihaz bağlı değilse komut gönderilmez; sonuç bu alanda raporlanır.": "No command is sent when no device is connected; results are reported here.",
    "NetOps, telefon ve komut olaylarının canlı akışı.": "Live feed of NetOps, phone, and command events.",
    "Yeni bildirim yok.": "No new notifications.",
    "Olay": "Event",
    "Bildirimleri yenile": "Refresh notifications",
    "Ayarlar": "Settings",
    "Native NetOps arayüzünün davranışlarını yönet.": "Manage Native NetOps interface behavior.",
    "Genel": "General",
    "Sistem": "System",
    "Pencere Yöneticisi": "Window Manager",
    "Netolab": "Netolab",
    "Güvenlik": "Security",
    "Güncellemeler": "Updates",
    "Hakkında": "About",
    "Ayarları kaydet": "Save settings",
    "Ayarlar kaydedildi": "Settings saved",
    "Otomatik kaydedildi": "Saved automatically",
    "Ayarlar uygulandı": "Settings applied",
    "Dil ve temel NetOps davranışları.": "Language and core NetOps behavior.",
    "Uygulama dili": "Application language",
    "Türkçe": "Turkish",
    "English": "English",
    "Live Mode'u açılışta başlat": "Start Live Mode at startup",
    "Yerel öğrenme modunu etkinleştir": "Enable local learning mode",
    "Yerel API erişimine izin ver": "Allow local API access",
    "Kaynak izleme ve arka plan servisleri.": "Resource monitoring and background services.",
    "CPU/RAM ve servis durumu Sistem Durumu sekmesinden izlenir.": "CPU/RAM and service status are monitored on the System Status page.",
    "Arka plan servislerini etkinleştir": "Enable background services",
    "Sistem durumunu yenile": "Refresh system status",
    "Tema, açılış animasyonu ve ses tercihleri.": "Theme, startup animation, and sound preferences.",
    "Tema": "Theme",
    "Koyu": "Dark",
    "Açık": "Light",
    "Renk teması": "Accent color",
    "Yeşil": "Green",
    "Mavi": "Blue",
    "Koyu mavi": "Dark blue",
    "Açılış animasyonunu etkinleştir": "Enable startup animation",
    "Açılış sesini etkinleştir": "Enable startup sound",
    "Açılış GIF'i seç": "Choose startup GIF",
    "Açılış sesini seç": "Choose startup sound",
    "Native NetOps penceresinin açılış davranışı.": "Native NetOps window startup behavior.",
    "Açılışta pencereyi büyüt": "Maximize window at startup",
    "Now Playing durumunu açılışta izle": "Monitor Now Playing at startup",
    "Yerel eklenti ve beceri altyapısı.": "Local plugin and skill infrastructure.",
    "Yerel Netolab bileşenlerini etkinleştir": "Enable local Netolab components",
    "Eklentiler kullanıcı onayı olmadan çalıştırılmaz.": "Plugins do not run without user approval.",
    "Onaylar ve yerel erişim seçenekleri.": "Approvals and local access options.",
    "Riskli işlemlerde onay iste": "Require approval for risky actions",
    "NetOps sürüm ve güncelleme tercihleri.": "NetOps version and update preferences.",
    "Açılışta güncellemeleri kontrol et": "Check for updates at startup",
    "Henüz kontrol edilmedi": "Not checked yet",
    "Güncellemeleri kontrol et": "Check for updates",
    "Kontrol isteği hazırlandı": "Update check prepared",
    "Güncellemeler kontrol ediliyor...": "Checking for updates...",
    "Güncelleme onayı": "Update confirmation",
    "Yeni güncelleme bulundu. Güncellemeyi yapılandırmak ister misiniz?": "A new update is available. Configure it now?",
    "Güncelleme iptal edildi": "Update cancelled",
    "Sistem güncel": "System is up to date",
    "Güncelleme yapılandırılıyor...": "Configuring update...",
    "Güncelleme yapılandırıldı": "Update configured",
    "Yeniden başlat": "Restart",
    "Yeniden başlatılıyor...": "Restarting...",
    "Güncelleme başarısız": "Update failed",
    "Güncelleme kontrolü başarısız": "Update check failed",
    "Kapatılamıyor: güncelleme devam ediyor": "Cannot close: update is in progress",
    "Yapılandırma": "Configuration",
    "Güncelleme yükleniyor...": "Loading update...",
    "Güncelleme yüklendi": "Update loaded",
    "Güncelleme merkezi": "Update center",
    "Son güncellemeyi geri al": "Roll back latest update",
    "Geri alma kontrol ediliyor...": "Checking rollback availability...",
    "Geri alma kaydı yok": "No rollback record",
    "Geri alma kaydı": "Rollback record",
    "Geri alma onayı": "Rollback confirmation",
    "Son güncellemenin güvenli yedeğine dönmek istiyor musunuz?": "Do you want to restore the safe backup from the latest update?",
    "Geri alma hazırlanıyor...": "Preparing rollback...",
    "Geri alma hazırlandı": "Rollback prepared",
    "Geri alma başarısız": "Rollback failed",
    "İşlem günlüğü burada görünür.": "The operation log appears here.",
    "NetOps native masaüstü arayüzü.": "Native NetOps desktop interface.",
    "PySide6 Qt Widgets tabanı": "Built on PySide6 Qt Widgets",
    "Sana nasıl yardımcı olabilirim?": "How can I help you?",
    "NETOPS  /  OPERATÖR MERKEZİ": "NETOPS  /  OPERATOR CENTER",
    "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim?": "Hello! I am NetOps. How can I help you?",
    "Mesajını yaz...": "Type your message...",
    "Gönder  →": "Send  →",
    "Mesajı gönder": "Send message",
    "Sen": "You",
    "NetOps hazır": "NetOps ready",
    "Albüm: bekleniyor": "Album: waiting",
    "Platform: bekleniyor": "Platform: waiting",
    "ŞU AN ÇALIYOR": "NOW PLAYING",
    "BEKLEME MODU": "STANDBY MODE",
    "Albüm": "Album",
    "Platform": "Platform",
    "Platform: bekleniyor": "Platform: waiting",
    "Bilinmiyor": "Unknown",
    "Şu an çalan parça olduğunda bilgiler burada görünür.": "Track information will appear here when music is playing.",
    "Now Playing hazır": "Now Playing is ready",
    "Süre bilgisi bekleniyor": "Waiting for duration",
    "Oynatılıyor": "Playing",
    "Durdur": "Stop",
    "Başlat": "Play",
    "Now Playing'i kapat  (Esc yerine)": "Close Now Playing  (instead of Esc)",
    "Ses: okunamadı": "Volume: unavailable",
    "Süre bilgisi bekleniyor": "Waiting for duration",
}

_NATIVE_TURKISH_TRANSLATIONS: dict[str, str] = {
    english: turkish for turkish, english in _NATIVE_ENGLISH_TRANSLATIONS.items()
}


def _translate_native_text(value: Any, language: str) -> str:
    text = str(value if value is not None else "")
    bullet_prefix = "•  "
    if text.startswith(bullet_prefix):
        return bullet_prefix + _translate_native_text(text[len(bullet_prefix):], language)
    if str(language).lower().startswith("en"):
        return _NATIVE_ENGLISH_TRANSLATIONS.get(text, text)
    return _NATIVE_TURKISH_TRANSLATIONS.get(text, text)


_LEGACY_THEME_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#09090B",
        "sidebar": "#111114",
        "card": "#1B1B20",
        "entry_bg": "#141418",
        "entry_border": "#34343C",
        "text_main": "#F4F4F5",
        "text_dim": "#A1A1AA",
        "button_hover": "#2A2A31",
    },
    "light": {
        "bg": "#F4F5F7",
        "sidebar": "#FFFFFF",
        "card": "#E8EAEF",
        "entry_bg": "#FFFFFF",
        "entry_border": "#C8CDD6",
        "text_main": "#18181B",
        "text_dim": "#64646F",
        "button_hover": "#D9DDE5",
    },
}

_LEGACY_ACCENTS = {
    "green": "#22C55E",
    "blue": "#3B82F6",
    "dark-blue": "#2563EB",
}


def _blend_hex(source: str, target: str, ratio: float) -> str:
    try:
        source_rgb = [int(source[index:index + 2], 16) for index in (1, 3, 5)]
        target_rgb = [int(target[index:index + 2], 16) for index in (1, 3, 5)]
        values = [round(a + (b - a) * ratio) for a, b in zip(source_rgb, target_rgb)]
        return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in values)
    except (TypeError, ValueError):
        return source


def native_theme_palette(settings: dict[str, Any] | None = None) -> dict[str, str]:
    """Translate the legacy NetOps theme settings into native Qt color tokens."""
    values = dict(settings or {})
    mode = "light" if str(values.get("tema", "dark")).lower() in {"light", "acik", "açık", "white"} else "dark"
    palette = dict(_LEGACY_THEME_PALETTES[mode])
    accent = _LEGACY_ACCENTS.get(str(values.get("renk_temasi", "blue")).lower(), _LEGACY_ACCENTS["blue"])
    palette.update(
        {
            "accent": accent,
            "accent_hover": _blend_hex(accent, "#000000" if mode == "light" else "#FFFFFF", 0.16),
            "accent_text": "#111114" if mode == "light" and accent == _LEGACY_ACCENTS["green"] else "#FFFFFF",
            "button_fg": palette["card"],
            "button_text": palette["text_main"],
            "neon": accent,
        }
    )
    return palette


def _display(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("error"):
            return f"Hata: {value['error']}"
        if value.get("ok") is False:
            return f"İşlem başarısız: {value.get('error', 'bilinmeyen hata')}"
    return str(value)


class NetOpsQtWindow(QMainWindow):
    """Native Qt Widgets window for the NetOps desktop services."""

    def __init__(self, backend: QtBackend | None = None) -> None:
        super().__init__()
        self.backend = backend or build_qt_backend()
        self._pages: dict[str, QWidget] = {}
        self._page_stack = QStackedWidget()
        self._navigation = QListWidget()
        self._status = QLabel("Hazır")
        self._chat_output = ChatTranscript()
        self._chat_input = QLineEdit()
        self._chat_composer: QFrame | None = None
        self._chat_send_button: QPushButton | None = None
        self._chat_mode_button: QPushButton | None = None
        self._chat_new_chat_button: QPushButton | None = None
        self._chat_hero_widgets: list[QWidget] = []
        self._chat_hero_logo: QLabel | None = None
        self._chat_response_queue: Queue[tuple[str, Any]] = Queue()
        self._chat_pending = False
        self._chat_response_timer = QTimer(self)
        self._chat_response_timer.setInterval(40)
        self._chat_response_timer.timeout.connect(self._poll_chat_response)
        self._chat_response_timer.start()
        self._remote_output = QPlainTextEdit()
        self._remote_input = QLineEdit()
        self._system_values: dict[str, list[QLabel]] = {}
        self._devices_table = QTableWidget()
        self._automations_table = QTableWidget()
        self._notifications_list = QListWidget()
        self._now_playing_values: dict[str, QLabel] = {}
        self._now_playing_cover = QLabel()
        self._now_playing_island = QLabel("♪  Müzik bekleniyor")
        self._now_playing_island_animation: QPropertyAnimation | None = None
        self._now_playing_island_text = ""
        self._now_playing_card: ClickableFrame | None = None
        self._now_playing_compact_cover: NowPlayingCover | None = None
        self._now_playing_compact_info: QWidget | None = None
        self._now_playing_compact_title: QLabel | None = None
        self._now_playing_compact_detail: QLabel | None = None
        self._now_playing_compact_album: QLabel | None = None
        self._now_playing_compact_progress: QSlider | None = None
        self._now_playing_compact_timeline: QLabel | None = None
        self._now_playing_compact_controls: QWidget | None = None
        self._now_playing_compact_previous: QPushButton | None = None
        self._now_playing_compact_play_pause: QPushButton | None = None
        self._now_playing_compact_next: QPushButton | None = None
        self._now_playing_compact_mute: QPushButton | None = None
        self._now_playing_compact_volume: QSlider | None = None
        self._now_playing_compact_volume_value: QLabel | None = None
        self._now_playing_compact_expanded = False
        self._now_playing_compact_expand_animation: QParallelAnimationGroup | None = None
        self._now_playing_compact_duration = 0.0
        self._now_playing_compact_track_key = ""
        self._now_playing_page_progress: QSlider | None = None
        self._now_playing_page_timeline: QLabel | None = None
        self._now_playing_page_duration = 0.0
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_label = QLabel("Ses: okunuyor")
        self._mute_button = QPushButton("Sessize al")
        self._now_playing_overlay: QWidget | None = None
        self._now_playing_overlay_values: dict[str, QLabel] = {}
        self._now_playing_overlay_cover: QLabel | None = None
        self._now_playing_overlay_platform: QLabel | None = None
        self._now_playing_overlay_album: QLabel | None = None
        self._now_playing_overlay_timeline: QLabel | None = None
        self._now_playing_overlay_progress: QProgressBar | None = None
        self._now_playing_overlay_volume_slider: QSlider | None = None
        self._now_playing_overlay_volume_label: QLabel | None = None
        self._now_playing_overlay_play_pause: QPushButton | None = None
        self._now_playing_overlay_mute: QPushButton | None = None
        self._now_playing_overlay_visualizer: QLabel | None = None
        self._now_playing_visualizer_phase = 0
        self._now_playing_visualizer_timer = QTimer(self)
        self._now_playing_visualizer_timer.setInterval(90)
        self._now_playing_visualizer_timer.timeout.connect(self._refresh_fullscreen_visualizer)
        self._now_playing_overlay_timer = QTimer(self)
        self._now_playing_overlay_timer.setInterval(native_now_playing_contract()["refresh_ms"])
        self._now_playing_overlay_timer.timeout.connect(self._refresh_now_playing_fullscreen)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._sidebar_chat_new_button: QPushButton | None = None
        self._sidebar_recent_title: QLabel | None = None
        self._sidebar_recent_list: QListWidget | None = None
        self._sidebar_resource_card: QGroupBox | None = None
        self._sidebar_resource_values: dict[str, QLabel] = {}
        self._sidebar_settings_button: QPushButton | None = None
        self._recent_chat_titles: list[str] = []
        self._sidebar_quick_actions: dict[str, QPushButton] = {}
        self._sidebar_plan_button: QPushButton | None = None
        self._sidebar_plan_status: QLabel | None = None
        self._sidebar_devices_value: QLabel | None = None
        self._sidebar_remote_value: QLabel | None = None
        self._sidebar_notification_button: QPushButton | None = None
        self._sidebar_activity_list: QListWidget | None = None
        self._sidebar_notification_count = 0
        self._top_status_buttons: dict[str, QPushButton] = {}
        self._command_bar = QMenuBar(self)
        self._command_bar_actions: dict[str, QAction] = {}
        self._page_history: list[str] = []
        self._page_history_index = -1
        self._history_navigation = False
        self._sidebar_widget: QWidget | None = None
        self._netops_root: QWidget | None = None
        self._sidebar_open = False
        self._sidebar_effect: QGraphicsOpacityEffect | None = None
        self._sidebar_animation: QParallelAnimationGroup | None = None
        self._sidebar_hover_timer = QTimer(self)
        self._sidebar_hover_timer.setInterval(native_sidebar_motion_contract()["poll_ms"])
        self._sidebar_hover_timer.timeout.connect(self._poll_sidebar_hover)
        self._sidebar_close_timer = QTimer(self)
        self._sidebar_close_timer.setSingleShot(True)
        self._sidebar_close_timer.timeout.connect(self._close_sidebar_if_clear)
        self._overflow_menu_action_texts: list[str] = []
        self._now_playing_toggle_action: QAction | None = None
        self._buttons_with_feedback: list[QPushButton] = []
        self._button_feedback_animations: dict[int, QPropertyAnimation] = {}
        self._navigation_animations: dict[int, QPropertyAnimation] = {}
        settings = self.backend.run("settings")
        self._settings_data: dict[str, Any] = dict(settings) if isinstance(settings, dict) else {}
        self._language = self._normalize_language(self._settings_data.get("dil", "tr"))
        self._native_palette = native_theme_palette(self._settings_data)
        self._settings_controls: dict[str, QWidget] = {}
        self._settings_status: QLabel | None = None
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(250)
        self._settings_save_timer.timeout.connect(self._auto_save_settings)
        self._settings_tabs: QTabWidget | None = None
        self._settings_animation: QPropertyAnimation | None = None
        self._settings_tab_animations: dict[int, QPropertyAnimation] = {}
        self._update_queue: Queue[tuple[str, Any]] = Queue()
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(80)
        self._update_timer.timeout.connect(self._poll_update_queue)
        self._update_timer.start()
        self._update_pending = False
        self._update_exit_requested = False
        self._update_plan_path = ""
        self._update_check_button: QPushButton | None = None
        self._update_status_label: QLabel | None = None
        self._update_progress: QProgressBar | None = None
        self._update_restart_button: QPushButton | None = None
        self._update_loading_overlay: QFrame | None = None
        self._update_loading_label: QLabel | None = None
        self._update_loading_progress: QProgressBar | None = None
        self._update_rollback_record: dict[str, Any] | None = None
        self._update_rollback_button: QPushButton | None = None
        self._update_rollback_status: QLabel | None = None
        self._update_log_view: QPlainTextEdit | None = None
        self._now_playing_timer = QTimer(self)
        self._now_playing_timer.setInterval(native_visual_contract()["now_playing_poll_ms"])
        self._now_playing_timer.timeout.connect(self._refresh_now_playing)
        self._system_timer = QTimer(self)
        self._system_timer.setInterval(native_visual_contract()["system_poll_ms"])
        self._system_timer.timeout.connect(self._refresh_system)
        self._startup_animation: QPropertyAnimation | None = None
        self._page_animation: QPropertyAnimation | None = None
        self._page_effect: QGraphicsOpacityEffect | None = None
        self._top_logo: QLabel | None = None
        self._logo_animation: QPropertyAnimation | None = None
        self._sidebar_animations: list[QPropertyAnimation] = []

        brand = native_brand_contract()
        logo_path = Path(__file__).with_name(brand["logo_file"])
        self.setWindowTitle(brand["window_title"])
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1180, 760)
        self._apply_native_visuals()
        self._build_command_bar()
        self._build_window()
        self._refresh_system()
        self._refresh_now_playing()
        self._refresh_notifications()
        self._now_playing_timer.start()
        self._system_timer.start()
        self._sidebar_hover_timer.start()
        self._apply_language()

    @staticmethod
    def _normalize_language(value: Any) -> str:
        return "en" if str(value or "").lower().startswith("en") else "tr"

    def _t(self, value: Any) -> str:
        return _translate_native_text(value, self._language)

    def _on_language_changed(self, _index: int = -1) -> None:
        control = self._settings_controls.get("dil")
        if not isinstance(control, QComboBox):
            return
        self._language = self._normalize_language(control.currentData())
        self._settings_data["dil"] = self._language
        self._apply_language()

    def _translate_actions(self, actions: list[QAction]) -> None:
        for action in actions:
            action.setText(self._t(action.text()))
            if action.toolTip():
                action.setToolTip(self._t(action.toolTip()))
            menu = action.menu()
            if menu is not None:
                self._translate_actions(menu.actions())

    def _apply_language(self) -> None:
        """Retranslate every native Qt surface without rebuilding the window."""
        for widget in (self, *self.findChildren(QWidget)):
            if isinstance(widget, QLabel):
                widget.setText(self._t(widget.text()))
            elif isinstance(widget, QPushButton):
                widget.setText(self._t(widget.text()))
                if widget.toolTip():
                    widget.setToolTip(self._t(widget.toolTip()))
            elif isinstance(widget, QCheckBox):
                widget.setText(self._t(widget.text()))
            elif isinstance(widget, QGroupBox):
                widget.setTitle(self._t(widget.title()))
            elif isinstance(widget, QLineEdit):
                widget.setPlaceholderText(self._t(widget.placeholderText()))
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlaceholderText(self._t(widget.placeholderText()))
            elif isinstance(widget, QComboBox):
                widget.blockSignals(True)
                for index in range(widget.count()):
                    widget.setItemText(index, self._t(widget.itemText(index)))
                widget.blockSignals(False)

        for tabs in (self, *self.findChildren(QTabWidget)):
            if isinstance(tabs, QTabWidget):
                if tabs is self._settings_tabs:
                    labels = (
                        ("General", "System", "Appearance", "Window Manager", "Netolab", "Security", "Updates", "About")
                        if self._language == "en"
                        else native_settings_sections()
                    )
                    for index, label in enumerate(labels[: tabs.count()]):
                        tabs.setTabText(index, label)
                else:
                    for index in range(tabs.count()):
                        tabs.setTabText(index, self._t(tabs.tabText(index)))

        for table in (self, *self.findChildren(QTableWidget)):
            if isinstance(table, QTableWidget):
                for index in range(table.columnCount()):
                    header = table.horizontalHeaderItem(index)
                    if header is not None:
                        header.setText(self._t(header.text()))

        self._translate_actions(self._command_bar.actions())
        self._update_sidebar_notification_badge(self._sidebar_notification_count)

    def _apply_native_visuals(self) -> None:
        radius = native_visual_contract()["button_radius_px"]
        sidebar_radius = native_sidebar_contract()["panel_radius_px"]
        palette = self._native_palette
        self.setStyleSheet(
            f"QMainWindow, QWidget#netopsRoot, QWidget#netopsPage {{ background: {palette['bg']}; color: {palette['text_main']}; }}"
            f"QPushButton {{ background: {palette['button_fg']}; color: {palette['button_text']}; border: 1px solid {palette['entry_border']}; border-radius: {radius}px; padding: 5px 10px; min-height: 24px; }}"
            f"QPushButton:hover {{ background: {palette['button_hover']}; border-color: {palette['accent']}; }}"
            f"QPushButton:pressed {{ background: {palette['accent']}; color: {palette['accent_text']}; border: 2px solid {palette['accent_hover']}; padding-top: 6px; }}"
            f"QWidget#netopsSidebar {{ background: {palette['sidebar']}; border: 1px solid {palette['entry_border']}; border-radius: {sidebar_radius}px; }}"
            f"QLabel#sidebarRecentTitle {{ color: {palette['text_dim']}; font-size: 11px; font-weight: 700; padding: 4px 3px; }}"
            f"QListWidget#sidebarChatHistory {{ background: transparent; color: {palette['text_main']}; border: none; padding: 3px 0; font-size: 12px; }}"
            f"QListWidget#sidebarChatHistory::item {{ padding: 7px 4px; border-radius: 6px; }}"
            f"QListWidget#sidebarChatHistory::item:hover {{ background: {palette['button_hover']}; }}"
            f"QListWidget#sidebarChatHistory::item:selected {{ background: {palette['accent']}; color: {palette['accent_text']}; }}"
            f"QGroupBox#sidebarQuickCard, QGroupBox#sidebarAiPlanCard, QGroupBox#sidebarDeviceCard, QGroupBox#sidebarActivityCard {{ background: {palette['entry_bg']}; border-color: {palette['entry_border']}; border-radius: 12px; padding: 10px 7px 7px; }}"
            f"QGroupBox#sidebarQuickCard::title, QGroupBox#sidebarAiPlanCard::title, QGroupBox#sidebarDeviceCard::title, QGroupBox#sidebarActivityCard::title {{ color: {palette['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}"
            f"QLabel#sidebarPlanHint, QLabel#sidebarSummaryLabel {{ color: {palette['text_dim']}; font-size: 10px; }}"
            f"QLabel#sidebarPlanStatus {{ color: {palette['accent']}; font-size: 10px; font-weight: 600; }}"
            f"QLabel#sidebarSummaryValue {{ color: {palette['text_main']}; font-size: 11px; font-weight: 700; }}"
            f"QListWidget#sidebarActivityList {{ background: transparent; border: none; padding: 0; font-size: 10px; }}"
            f"QPushButton#sidebarNotificationButton {{ border-color: {palette['accent']}; }}"
            f"QLabel#nowPlayingIsland {{ background: {palette['card']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; border-radius: 15px; padding: 6px 14px; }}"
            f"QFrame#nowPlayingCompactCard {{ background: {palette['card']}; border: 1px solid {palette['entry_border']}; border-radius: 18px; padding: 4px 8px; }}"
            f"QFrame#nowPlayingCompactCard[compact=\"true\"] {{ border-radius: 40px; padding: 0; }}"
            f"QFrame#nowPlayingCompactCard:hover {{ background: {palette['button_hover']}; border-color: {palette['accent']}; }}"
            f"QLabel#nowPlayingCompactTitle {{ color: {palette['text_main']}; font-weight: 700; }}"
            f"QLabel#nowPlayingCompactDetail, QLabel#nowPlayingCompactAlbum, QLabel#nowPlayingCompactTimeline, QLabel#nowPlayingCompactVolumeValue {{ color: {palette['text_dim']}; }}"
            f"QSlider#nowPlayingCompactProgress {{ min-height: 12px; }}"
            f"QWidget#nowPlayingCompactControls QPushButton {{ min-width: 52px; min-height: 42px; padding: 6px 12px; border-radius: 21px; font-size: 16px; font-weight: 700; }}"
            f"QWidget#nowPlayingCompactControls QSlider {{ min-height: 12px; }}"
            f"QSlider#nowPlayingCompactVolume {{ min-width: 150px; max-width: 190px; min-height: 12px; }}"
            f"QPushButton#nowPlayingCompactMute {{ min-height: 30px; padding: 4px 10px; border-radius: 10px; }}"
            f"QGroupBox {{ background: {palette['card']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; border-radius: 10px; margin-top: 10px; padding: 12px 8px 8px; }}"
            f"QGroupBox::title {{ color: {palette['text_dim']}; subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
            f"QPlainTextEdit, QLineEdit, QComboBox, QListWidget, QTableWidget {{ background: {palette['entry_bg']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; border-radius: 8px; padding: 6px; selection-background-color: {palette['accent']}; selection-color: {palette['accent_text']}; }}"
            f"QTabWidget::pane {{ background: {palette['bg']}; border: 1px solid {palette['entry_border']}; border-radius: 8px; top: -1px; }}"
            f"QTabBar {{ background: transparent; }}"
            f"QTabBar::tab {{ background: transparent; color: {palette['text_dim']}; border: 1px solid transparent; border-radius: 7px; padding: 9px 14px; min-height: 34px; margin-right: 4px; }}"
            f"QTabBar::tab:hover {{ background: {palette['button_hover']}; color: {palette['text_main']}; border-color: {palette['entry_border']}; }}"
            f"QTabBar::tab:selected {{ background: {palette['accent']}; color: {palette['accent_text']}; border-color: {palette['accent']}; font-weight: 600; }}"
            f"QTabBar::tab:focus {{ outline: none; border-color: {palette['accent_hover']}; }}"
            f"QCheckBox {{ color: {palette['text_main']}; spacing: 8px; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; background: {palette['entry_bg']}; border: 1px solid {palette['entry_border']}; border-radius: 4px; }}"
            f"QCheckBox::indicator:hover {{ border-color: {palette['accent']}; }}"
            f"QCheckBox::indicator:checked {{ background: {palette['accent']}; border-color: {palette['accent']}; }}"
            f"QAbstractItemView::item:selected {{ background: {palette['accent']}; color: {palette['accent_text']}; }}"
            f"QComboBox QAbstractItemView {{ background: {palette['entry_bg']}; color: {palette['text_main']}; selection-background-color: {palette['accent']}; selection-color: {palette['accent_text']}; }}"
            f"QSlider::groove:horizontal {{ background: {palette['entry_border']}; height: 4px; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ background: {palette['accent']}; width: 14px; margin: -5px 0; border-radius: 7px; }}"
            f"QScrollBar:vertical {{ background: {palette['entry_bg']}; width: 10px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {palette['entry_border']}; border-radius: 5px; min-height: 24px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {palette['accent']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            f"QMenuBar#netopsCommandBar {{ background: {palette['sidebar']}; color: {palette['text_dim']}; border-bottom: 1px solid {palette['entry_border']}; padding: 0 6px; spacing: 4px; }}"
            f"QMenuBar#netopsCommandBar::item {{ background: transparent; color: {palette['text_dim']}; padding: 8px 12px; margin: 0 1px; }}"
            f"QMenuBar#netopsCommandBar::item:selected {{ background: {palette['button_hover']}; color: {palette['text_main']}; border-radius: 6px; }}"
            f"QMenu {{ background: {palette['card']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; padding: 5px; }}"
            f"QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 5px; }}"
            f"QMenu::item:selected {{ background: {palette['accent']}; color: {palette['accent_text']}; }}"
            f"QProgressBar {{ background: {palette['entry_bg']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; border-radius: 7px; text-align: center; }}"
            f"QProgressBar::chunk {{ background: {palette['accent']}; border-radius: 6px; }}"
            f"QScrollArea#chatOutput {{ background: transparent; border: none; border-radius: 0; }}"
            f"QWidget#chatTranscriptSurface {{ background: transparent; }}"
            f"QFrame#chatUserBubble {{ background: {palette['accent']}; color: {palette['accent_text']}; border: none; border-radius: 18px; }}"
            f"QFrame#chatAssistantBubble {{ background: {palette['card']}; color: {palette['text_main']}; border: 1px solid {palette['entry_border']}; border-radius: 18px; }}"
            f"QLabel#chatBubbleSender {{ color: {palette['accent']}; font-size: 10px; font-weight: 700; }}"
            f"QFrame#chatUserBubble QLabel#chatBubbleText {{ color: {palette['accent_text']}; padding: 0; font-size: 13px; }}"
            f"QFrame#chatAssistantBubble QLabel#chatBubbleText {{ color: {palette['text_main']}; padding: 0; font-size: 13px; }}"
            f"QLabel#chatHeroKicker {{ color: {palette['text_dim']}; font-size: 11px; letter-spacing: 1px; padding: 0 0 4px; }}"
            f"QLabel#chatHeroGreeting {{ color: {palette['text_dim']}; font-size: 13px; padding: 0 0 10px; }}"
            f"QFrame#chatTypingBubble {{ background: {palette['card']}; border: 1px solid {palette['entry_border']}; border-radius: 18px; }}"
            f"QLabel#chatTypingLabel {{ color: {palette['text_dim']}; min-width: 42px; }}"
            f"QFrame#chatComposer {{ background: {palette['entry_bg']}; border: 1px solid {palette['entry_border']}; border-radius: 24px; padding: 5px; }}"
            f"QFrame#chatComposer:focus-within {{ border-color: {palette['accent']}; }}"
            f"QLineEdit#chatComposerInput {{ background: transparent; color: {palette['text_main']}; border: none; padding: 8px 12px; min-height: 38px; selection-background-color: {palette['accent']}; selection-color: {palette['accent_text']}; }}"
            f"QLineEdit#chatComposerInput:focus {{ border: none; }}"
            f"QPushButton#chatNewChatButton {{ background: transparent; color: {palette['text_dim']}; border: none; border-radius: 19px; min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px; padding: 0; font-size: 23px; font-weight: 400; }}"
            f"QPushButton#chatNewChatButton:hover {{ background: {palette['button_hover']}; color: {palette['text_main']}; }}"
            f"QPushButton#chatNewChatButton:pressed {{ background: {palette['accent']}; color: {palette['accent_text']}; }}"
            f"QPushButton#chatSendButton {{ background: {palette['accent']}; color: {palette['accent_text']}; border: none; border-radius: 16px; min-width: 86px; min-height: 40px; padding: 5px 16px; font-weight: 700; }}"
            f"QPushButton#chatSendButton:hover {{ background: {palette['accent_hover']}; border: none; }}"
            f"QPushButton#chatSendButton:pressed {{ background: {palette['accent_hover']}; padding-top: 6px; }}"
        )

    def _build_command_bar(self) -> None:
        contract = native_command_bar_contract()
        self._command_bar.setObjectName("netopsCommandBar")
        self._command_bar.setFixedHeight(int(contract["height_px"]))
        self._command_bar.setNativeMenuBar(False)

        for label, handler, icon_name in (
            ("Geri", lambda: self._navigate_history(-1), "back"),
            ("İleri", lambda: self._navigate_history(1), "forward"),
            ("Görünüm", self._toggle_window_view, "view"),
        ):
            action = self._command_bar.addAction(label)
            action.setIcon(netops_icon(icon_name, size=16))
            action.setToolTip(label.title())
            action.triggered.connect(handler)
            self._command_bar_actions[label] = action

        file_menu = self._command_bar.addMenu("Dosya")
        file_menu.addAction("Yeni sohbet", self._start_new_chat)
        file_menu.addAction("Kapat", self.close)

        edit_menu = self._command_bar.addMenu("Düzenle")
        edit_menu.addAction("Sohbeti temizle", self._clear_chat_output)
        edit_menu.addAction("Sohbeti kopyala", self._copy_chat_output)
        self._now_playing_toggle_action = edit_menu.addAction("Now Playing'i aç/kapat")
        self._now_playing_toggle_action.setCheckable(True)
        self._now_playing_toggle_action.setChecked(True)
        self._now_playing_toggle_action.triggered.connect(self._set_now_playing_enabled)

        view_menu = self._command_bar.addMenu("Görünüm")
        view_menu.addAction("Kenar çubuğunu göster/gizle", self._toggle_sidebar)
        view_menu.addAction("Tam ekran görünümü", self._toggle_window_view)

        help_menu = self._command_bar.addMenu("Yardım")
        help_menu.addAction("OpsCenter QR kodu", self._show_opscenter_qr)
        help_menu.addAction("Ayarları aç", lambda: self._open_native_page("settings"))
        help_menu.addAction("NetOps hakkında", lambda: self._open_native_page("settings"))

        overflow_menu = self._command_bar.addMenu("...")
        for label, route in (
            ("Now Playing", "now_playing"),
            ("Cihazlar", "devices"),
            ("Otomasyonlar", "automations"),
            ("Sistem", "system"),
            ("Remote", "remote"),
            ("Bildirimler", "notifications"),
            ("Ayarlar", "settings"),
        ):
            overflow_menu.addAction(label, lambda _checked=False, target=route: self._open_native_page(target))
            self._overflow_menu_action_texts.append(label)
        self.setMenuBar(self._command_bar)

    def _opscenter_qr_pixmap(self) -> QPixmap:
        try:
            import qrcode

            image = qrcode.make(native_help_center_contract()["url"])
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            pixmap = QPixmap.fromImage(QImage.fromData(buffer.getvalue(), "PNG"))
            return pixmap.scaled(248, 248, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        except Exception:
            return QPixmap()

    def _show_opscenter_qr(self) -> None:
        contract = native_help_center_contract()
        dialog = QDialog(self)
        dialog.setWindowTitle(contract["name"])
        dialog.setMinimumWidth(470)
        layout = QHBoxLayout(dialog)
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr = self._opscenter_qr_pixmap()
        if not qr.isNull():
            qr_label.setPixmap(qr)
        else:
            qr_label.setText(self._t("QR kodu oluşturulamadı"))
        text_box = QVBoxLayout()
        title = QLabel(contract["name"])
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        instruction = QLabel(self._t(contract["instruction"]))
        instruction.setWordWrap(True)
        url = QLabel(contract["url"])
        url.setWordWrap(True)
        url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        close_button = QPushButton(self._t("Kapat"))
        close_button.clicked.connect(dialog.accept)
        text_box.addWidget(title)
        text_box.addSpacing(8)
        text_box.addWidget(instruction)
        text_box.addSpacing(8)
        text_box.addWidget(url)
        text_box.addStretch(1)
        text_box.addWidget(close_button)
        layout.addWidget(qr_label)
        layout.addLayout(text_box, 1)
        dialog.exec()

    def _start_new_chat(self) -> None:
        self._clear_chat_output()
        self._set_chat_hero_visible(True)
        self._open_native_page("chat")
        self._chat_output.appendPlainText(self._t("NetOps: Yeni sohbet hazır."))

    def _clear_chat_output(self) -> None:
        self._chat_output.clear()

    def _copy_chat_output(self) -> None:
        QApplication.clipboard().setText(self._chat_output.toPlainText())

    def _toggle_sidebar(self) -> None:
        self._set_sidebar_open(not self._sidebar_open)

    def _sidebar_positions(self) -> tuple[QPoint, QPoint] | None:
        if self._sidebar_widget is None or self._netops_root is None:
            return None
        width = self._sidebar_widget.width() or 286
        top = 8
        return QPoint(8, top), QPoint(-width - 2, top)

    def _position_sidebar_overlay(self, *, closed: bool | None = None) -> None:
        if self._sidebar_widget is None or self._netops_root is None:
            return
        root = self._netops_root
        width = self._sidebar_widget.width() or 286
        height = max(1, root.height() - 16)
        self._sidebar_widget.setGeometry(self._sidebar_widget.x(), 8, width, height)
        positions = self._sidebar_positions()
        if positions is None:
            return
        open_pos, closed_pos = positions
        if closed is True:
            self._sidebar_widget.move(closed_pos)
        elif closed is False:
            self._sidebar_widget.move(open_pos)

    def _finish_sidebar_animation(self, animation: QParallelAnimationGroup, opening: bool) -> None:
        if self._sidebar_animation is not animation:
            return
        self._sidebar_animation = None
        if not opening and self._sidebar_widget is not None:
            self._sidebar_widget.hide()
        animation.deleteLater()

    def _set_sidebar_open(self, opened: bool, *, animate: bool = True) -> None:
        if self._sidebar_widget is None or self._netops_root is None:
            return
        opened = bool(opened)
        if opened == self._sidebar_open and (opened or self._sidebar_widget.isHidden()):
            return
        self._sidebar_close_timer.stop()
        self._sidebar_open = opened
        if self._sidebar_animation is not None:
            self._sidebar_animation.stop()
            self._sidebar_animation.deleteLater()
            self._sidebar_animation = None

        positions = self._sidebar_positions()
        if positions is None:
            return
        open_pos, closed_pos = positions
        reduced_motion = os.environ.get("NETOPS_REDUCE_MOTION") == "1"
        if self._sidebar_effect is None:
            self._sidebar_effect = QGraphicsOpacityEffect(self._sidebar_widget)
            self._sidebar_widget.setGraphicsEffect(self._sidebar_effect)

        if not animate or reduced_motion:
            self._position_sidebar_overlay(closed=not opened)
            self._sidebar_effect.setOpacity(1.0 if opened else 0.0)
            self._sidebar_widget.setVisible(opened)
            if opened:
                self._sidebar_widget.raise_()
            return

        self._sidebar_widget.setVisible(True)
        self._sidebar_widget.raise_()
        if opened:
            self._sidebar_widget.move(closed_pos)
            self._sidebar_effect.setOpacity(0.0)
        animation = QParallelAnimationGroup(self)
        position_animation = QPropertyAnimation(self._sidebar_widget, b"pos", animation)
        position_animation.setStartValue(self._sidebar_widget.pos())
        position_animation.setEndValue(open_pos if opened else closed_pos)
        position_animation.setDuration(
            native_sidebar_motion_contract()["open_ms" if opened else "close_ms"]
        )
        position_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity_animation = QPropertyAnimation(self._sidebar_effect, b"opacity", animation)
        opacity_animation.setStartValue(self._sidebar_effect.opacity())
        opacity_animation.setEndValue(1.0 if opened else 0.0)
        opacity_animation.setDuration(
            native_sidebar_motion_contract()["open_ms" if opened else "close_ms"]
        )
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.addAnimation(position_animation)
        animation.addAnimation(opacity_animation)
        animation.finished.connect(lambda: self._finish_sidebar_animation(animation, opened))
        self._sidebar_animation = animation
        animation.start()

    def _sidebar_pointer_state(self) -> tuple[bool, bool]:
        if self._sidebar_widget is None or self._netops_root is None:
            return False, False
        pointer = QCursor.pos()
        root_point = self._netops_root.mapFromGlobal(pointer)
        inside_root = self._netops_root.rect().contains(root_point)
        inside_sidebar = self._sidebar_widget.isVisible() and self._sidebar_widget.geometry().contains(root_point)
        near_edge = inside_root and root_point.x() <= native_sidebar_motion_contract()["edge_trigger_px"]
        return near_edge, inside_sidebar

    def _poll_sidebar_hover(self) -> None:
        if self._sidebar_widget is None or self._netops_root is None or not self.isVisible():
            return
        near_edge, inside_sidebar = self._sidebar_pointer_state()
        if near_edge or inside_sidebar:
            self._sidebar_close_timer.stop()
            if not self._sidebar_open:
                self._set_sidebar_open(True)
            return
        if self._sidebar_open and not self._sidebar_close_timer.isActive():
            self._sidebar_close_timer.start(220)

    def _close_sidebar_if_clear(self) -> None:
        near_edge, inside_sidebar = self._sidebar_pointer_state()
        if not near_edge and not inside_sidebar:
            self._set_sidebar_open(False)

    def _toggle_window_view(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _set_now_playing_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        button = self._top_status_buttons.get("NOW PLAYING")
        if button is not None:
            button.setVisible(enabled)
        if enabled:
            self._now_playing_timer.start()
            self._refresh_now_playing()
        else:
            self._now_playing_timer.stop()
            if self._page_stack.currentWidget() is self._pages.get("now_playing"):
                self._open_native_page("chat")

    def _open_now_playing_settings(self) -> None:
        self._open_native_page("settings")
        tabs = self._settings_tabs
        if tabs is None:
            return
        target_titles = {"Pencere Yöneticisi", self._t("Pencere Yöneticisi")}
        for index in range(tabs.count()):
            if tabs.tabText(index) in target_titles:
                tabs.setCurrentIndex(index)
                return

    def _navigate_history(self, offset: int) -> None:
        target = self._page_history_index + int(offset)
        if target < 0 or target >= len(self._page_history):
            return
        self._history_navigation = True
        try:
            self._open_native_page(self._page_history[target])
            self._page_history_index = target
        finally:
            self._history_navigation = False

    def _build_now_playing_compact_card(self) -> ClickableFrame:
        card = ClickableFrame()
        card.setObjectName("nowPlayingCompactCard")
        card.setMinimumWidth(76)
        card.setMaximumWidth(76)
        card.setMinimumHeight(76)
        card.setMaximumHeight(76)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card.setProperty("compact", True)
        card.setToolTip("Now Playing kontrollerini aç")
        card.clicked.connect(self._toggle_compact_controls)
        card.doubleClicked.connect(self._open_now_playing_fullscreen)
        card.longPressed.connect(self._open_now_playing_settings)
        card.mouseLeft.connect(self._collapse_compact_controls)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        cover = NowPlayingCover(card)
        cover.setObjectName("nowPlayingCompactCover")
        cover.set_compact_circle(True)
        cover.clear_art("♪")
        layout.addWidget(cover, 0, Qt.AlignmentFlag.AlignVCenter)

        info_widget = QWidget(card)
        info_widget.setObjectName("nowPlayingCompactInfo")
        info = QVBoxLayout(info_widget)
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        title = QLabel(self._t("Müzik bekleniyor"), card)
        title.setObjectName("nowPlayingCompactTitle")
        title.setStyleSheet("font-size: 11px; font-weight: 700;")
        detail = QLabel(self._t("Kaynak bilgisi yok"), card)
        detail.setObjectName("nowPlayingCompactDetail")
        detail.setStyleSheet("font-size: 10px;")
        album = QLabel(self._t("Albüm: bekleniyor"), card)
        album.setObjectName("nowPlayingCompactAlbum")
        album.setStyleSheet("font-size: 10px;")

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(title, 1)
        volume = QSlider(Qt.Orientation.Horizontal, card)
        volume.setObjectName("nowPlayingCompactVolume")
        volume.setRange(0, 100)
        volume.setValue(0)
        volume.setMinimumWidth(150)
        volume.setMaximumWidth(190)
        volume.setToolTip(self._t("Ses seviyesi"))
        volume.sliderReleased.connect(self._set_compact_volume)
        volume_value = QLabel("—", card)
        volume_value.setObjectName("nowPlayingCompactVolumeValue")
        volume_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        volume_value.setMinimumWidth(34)
        mute = QPushButton(self._t("Sessize al"), card)
        mute.setObjectName("nowPlayingCompactMute")
        mute.setToolTip(self._t("Sessize al"))
        mute.clicked.connect(self._toggle_compact_mute)
        title_row.addWidget(volume, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(volume_value, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(mute, 0, Qt.AlignmentFlag.AlignVCenter)
        info.addLayout(title_row)
        info.addWidget(detail)
        info.addWidget(album)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress = QSlider(Qt.Orientation.Horizontal, card)
        progress.setObjectName("nowPlayingCompactProgress")
        progress.setRange(0, 1000)
        progress.setValue(0)
        progress.sliderMoved.connect(self._preview_compact_position)
        progress.sliderReleased.connect(self._set_compact_position)
        timeline = QLabel("00:00 / 00:00", card)
        timeline.setObjectName("nowPlayingCompactTimeline")
        timeline.setMinimumWidth(112)
        timeline.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(progress, 1)
        progress_row.addWidget(timeline)
        info.addLayout(progress_row)

        controls = QWidget(card)
        controls.setObjectName("nowPlayingCompactControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        previous = QPushButton(controls)
        previous.setIcon(netops_icon("previous", size=18))
        previous.setToolTip(self._t("Önceki"))
        previous.clicked.connect(lambda: self._media_action("previous"))
        play_pause = QPushButton(controls)
        play_pause.setIcon(netops_icon("play", size=18))
        play_pause.setToolTip(self._t("Oynat / Duraklat"))
        play_pause.clicked.connect(lambda: self._media_action("play_pause"))
        next_button = QPushButton(controls)
        next_button.setIcon(netops_icon("next", size=18))
        next_button.setToolTip(self._t("Sonraki"))
        next_button.clicked.connect(lambda: self._media_action("next"))
        for button in (previous, play_pause, next_button):
            button.setMinimumSize(52, 42)
        controls_layout.addWidget(previous)
        controls_layout.addWidget(play_pause)
        controls_layout.addWidget(next_button)
        controls.setVisible(False)
        info.addWidget(controls)
        info_widget.hide()
        layout.addWidget(info_widget, 1)

        self._now_playing_card = card
        self._now_playing_compact_cover = cover
        self._now_playing_compact_info = info_widget
        self._now_playing_compact_title = title
        self._now_playing_compact_detail = detail
        self._now_playing_compact_album = album
        self._now_playing_compact_progress = progress
        self._now_playing_compact_timeline = timeline
        self._now_playing_compact_controls = controls
        self._now_playing_compact_previous = previous
        self._now_playing_compact_play_pause = play_pause
        self._now_playing_compact_next = next_button
        self._now_playing_compact_mute = mute
        self._now_playing_compact_volume = volume
        self._now_playing_compact_volume_value = volume_value
        return card

    def _build_window(self) -> None:
        root = QWidget()
        root.setObjectName("netopsRoot")
        self._netops_root = root
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)

        status_bar = QHBoxLayout()
        top_routes = {
            "SİSTEM": "system",
            "REMOTE": "remote",
            "BİLDİRİMLER": "notifications",
            "NOW PLAYING": "now_playing",
        }
        def add_top_button(label: str) -> None:
            button = QPushButton(f"•  {label}")
            button.setFlat(True)
            button.clicked.connect(lambda _checked=False, route=top_routes[label]: self._open_native_page(route))
            self._top_status_buttons[label] = button
            status_bar.addWidget(button)

        top_status = native_legacy_layout_contract()["top_status"]
        for label in top_status[:-1]:
            add_top_button(label)
            self._top_status_buttons[label].setVisible(False)
        status_bar.addStretch(1)
        now_playing_card = self._build_now_playing_compact_card()
        self._top_status_buttons[top_status[-1]] = now_playing_card
        status_bar.addWidget(now_playing_card)
        self._now_playing_island.setObjectName("nowPlayingIsland")
        self._now_playing_island.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._now_playing_island.setMinimumSize(380, 42)
        self._now_playing_island.setToolTip("Now Playing durumu")
        layout.addLayout(status_bar)

        body = QHBoxLayout()
        self._sidebar_widget = self._build_sidebar()

        for key, _label in _PAGES:
            page = getattr(self, f"_build_{key}_page")()
            self._pages[key] = page
            self._page_stack.addWidget(page)
        body.addWidget(self._page_stack, 1)
        layout.addLayout(body, 1)
        self.setCentralWidget(root)
        self._sidebar_widget.setParent(root)
        self._sidebar_widget.setFixedWidth(286)
        self._position_sidebar_overlay(closed=True)
        self._sidebar_effect = QGraphicsOpacityEffect(self._sidebar_widget)
        self._sidebar_effect.setOpacity(0.0)
        self._sidebar_widget.setGraphicsEffect(self._sidebar_effect)
        self._sidebar_widget.hide()
        self._buttons_with_feedback = root.findChildren(QPushButton)
        for button in self._buttons_with_feedback:
            button.clicked.connect(lambda _checked=False, target=button: self._animate_button_feedback(target))
        self._start_intro_animations()
        self._open_native_page("chat")
        self.statusBar().hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._sidebar_widget is not None:
            self._position_sidebar_overlay(closed=not self._sidebar_open)
        if self._update_loading_overlay is not None and self._netops_root is not None:
            self._update_loading_overlay.setGeometry(self._netops_root.rect())

    def _start_intro_animations(self) -> None:
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return

        if self._top_logo is not None:
            effect = QGraphicsOpacityEffect(self._top_logo)
            effect.setOpacity(0.15)
            self._top_logo.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(native_animation_contract()["logo_fade_ms"])
            animation.setStartValue(0.15)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            self._logo_animation = animation

        self._sidebar_animations = []
        stagger = native_animation_contract()["sidebar_stagger_ms"]
        for index, button in enumerate(self._nav_buttons.values()):
            QTimer.singleShot(index * stagger, lambda target=button: self._animate_sidebar_button_in(target))

    def _animate_sidebar_button_in(self, button: QPushButton) -> None:
        if not button or os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return
        effect = QGraphicsOpacityEffect(button)
        effect.setOpacity(0.0)
        button.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(native_motion_contract()["page_ms"])
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._sidebar_animations.append(animation)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("netopsSidebar")
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(290)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        new_chat = QPushButton("＋  Yeni sohbet")
        new_chat.setIcon(self._sidebar_icon("message"))
        new_chat.setToolTip("Yeni sohbet")
        new_chat.clicked.connect(self._start_new_chat)
        self._sidebar_chat_new_button = new_chat
        layout.addWidget(new_chat)

        resource_card = QGroupBox("Sistem durumu")
        resource_card.setObjectName("sidebarResourceCard")
        resource_layout = QFormLayout(resource_card)
        resource_layout.setContentsMargins(8, 10, 8, 8)
        resource_layout.setVerticalSpacing(6)
        for key, label_text in (("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU")):
            value = QLabel("Ölçülüyor")
            value.setObjectName(f"sidebarResourceValue_{key}")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar_resource_values[key] = value
            self._system_values.setdefault(key, []).append(value)
            resource_layout.addRow(QLabel(label_text), value)
        self._sidebar_resource_card = resource_card
        layout.addWidget(resource_card)

        recent_title = QLabel("Yakın zamanlar")
        recent_title.setObjectName("sidebarRecentTitle")
        self._sidebar_recent_title = recent_title
        layout.addWidget(recent_title)

        recent_list = QListWidget()
        recent_list.setObjectName("sidebarChatHistory")
        recent_list.setSpacing(1)
        recent_list.setFrameShape(QFrame.Shape.NoFrame)
        recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        recent_list.itemClicked.connect(self._select_recent_chat)
        self._sidebar_recent_list = recent_list
        layout.addWidget(recent_list, 1)
        self._load_recent_chat_titles()
        self._render_recent_chat_titles()
        layout.addStretch(1)

        settings = QPushButton("Ayarlar")
        settings.setObjectName("sidebarSettingsButton")
        settings.setIcon(self._sidebar_icon("settings"))
        settings.setToolTip("Ayarlar")
        settings.clicked.connect(lambda: self._open_native_page("settings"))
        self._sidebar_settings_button = settings
        layout.addWidget(settings)
        return sidebar

    def _load_recent_chat_titles(self) -> None:
        """Load user prompts as lightweight recent-chat labels."""
        candidates = (
            Path(__file__).with_name("chat_history.json"),
            Path.cwd() / "chat_history.json",
        )
        messages: list[Any] = []
        for path in candidates:
            try:
                if path.is_file():
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    messages = payload.get("messages", []) if isinstance(payload, dict) else []
                    break
            except (OSError, ValueError, TypeError):
                continue
        titles: list[str] = []
        seen: set[str] = set()
        for message in reversed(messages if isinstance(messages, list) else []):
            if not isinstance(message, dict) or str(message.get("role", "")).lower() not in {"user", "human"}:
                continue
            title = " ".join(str(message.get("text", "") or "").split()).strip()
            if not title or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            titles.append(title[:96] + ("..." if len(title) > 96 else ""))
            if len(titles) >= int(native_sidebar_chat_contract()["max_items"]):
                break
        self._recent_chat_titles = titles

    def _render_recent_chat_titles(self) -> None:
        if self._sidebar_recent_list is None:
            return
        self._sidebar_recent_list.clear()
        if not self._recent_chat_titles:
            self._sidebar_recent_list.addItem(self._t("Henüz sohbet yok."))
            return
        for title in self._recent_chat_titles:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, title)
            item.setToolTip(title)
            self._sidebar_recent_list.addItem(item)

    def _remember_recent_chat(self, text: str) -> None:
        title = " ".join(str(text or "").split()).strip()
        if not title:
            return
        title = title[:96] + ("..." if len(title) > 96 else "")
        self._recent_chat_titles = [
            item for item in self._recent_chat_titles if item.casefold() != title.casefold()
        ]
        self._recent_chat_titles.insert(0, title)
        self._recent_chat_titles = self._recent_chat_titles[: int(native_sidebar_chat_contract()["max_items"])]
        self._render_recent_chat_titles()

    def _select_recent_chat(self, item: QListWidgetItem) -> None:
        title = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not title:
            return
        self._open_native_page("chat")
        self._chat_input.setText(title)
        self._chat_input.setFocus()

    def _sidebar_icon(self, route: str):
        icons = {
            "chat": "message",
            "devices": "devices",
            "now_playing": "media",
            "automations": "workflow",
            "remote": "remote",
            "system": "system",
            "settings": "settings",
        }
        return netops_icon(icons.get(route, "system"), size=16)

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("netopsPage")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(title))
        layout.addWidget(QLabel(subtitle))
        return page, layout

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("netopsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(38, 28, 38, 18)
        logo = QLabel(page)
        logo.setObjectName("netopsHeroLogo")
        logo_path = str(Path(__file__).with_name("Logo.png"))
        pixmap = _remove_logo_background(QPixmap(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    170,
                    170,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo.setText("▲")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chat_hero_logo = logo
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Sana nasıl yardımcı olabilirim?")
        title.setObjectName("chatHeroTitle")
        title.setStyleSheet("padding: 6px 0 14px;")
        title_font = title.font()
        title_font.setPointSize(26)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self._chat_hero_title = title

        subtitle = QLabel("NETOPS  /  OPERATÖR MERKEZİ")
        subtitle.setObjectName("chatHeroKicker")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        self._chat_hero_subtitle = subtitle

        greeting = QLabel("Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim?")
        greeting.setObjectName("chatHeroGreeting")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(greeting)
        self._chat_hero_greeting = greeting

        self._chat_hero_widgets = [logo, title, subtitle, greeting]

        self._chat_output.setReadOnly(True)
        self._chat_output.setObjectName("chatOutput")
        self._chat_output.setMaximumWidth(1100)
        self._chat_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        transcript_holder = QWidget(page)
        transcript_holder_layout = QHBoxLayout(transcript_holder)
        transcript_holder_layout.setContentsMargins(0, 0, 0, 0)
        transcript_holder_layout.addStretch(1)
        transcript_holder_layout.addWidget(self._chat_output, 100)
        transcript_holder_layout.addStretch(1)
        layout.addWidget(transcript_holder, 1)

        composer = QFrame()
        composer.setObjectName("chatComposer")
        composer.setMaximumWidth(1100)
        composer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(8, 6, 8, 6)
        composer_layout.setSpacing(8)

        new_chat = QPushButton("+")
        new_chat.setObjectName("chatNewChatButton")
        new_chat.setToolTip("Yeni sohbet")
        new_chat.setAccessibleName("Yeni sohbet")
        new_chat.clicked.connect(self._start_new_chat)
        self._chat_new_chat_button = new_chat

        self._chat_input.setPlaceholderText("Mesajını yaz...")
        self._chat_input.setObjectName("chatComposerInput")
        self._chat_input.setMinimumHeight(40)
        self._chat_input.returnPressed.connect(self._submit_chat)
        send = QPushButton("Gönder")
        send.setObjectName("chatSendButton")
        send.setToolTip("Mesajı gönder")
        send.setAccessibleName("Mesajı gönder")
        send.setIcon(netops_icon("send", size=16))
        send.setIconSize(QSize(16, 16))
        send.clicked.connect(self._submit_chat)
        composer_layout.addWidget(new_chat)
        composer_layout.addWidget(self._chat_input, 1)
        composer_layout.addWidget(send)
        self._chat_composer = composer
        self._chat_send_button = send
        composer_holder = QWidget(page)
        composer_holder_layout = QHBoxLayout(composer_holder)
        composer_holder_layout.setContentsMargins(0, 0, 0, 0)
        composer_holder_layout.addStretch(1)
        composer_holder_layout.addWidget(composer, 100)
        composer_holder_layout.addStretch(1)
        layout.addWidget(composer_holder)
        return page

    def _set_chat_hero_visible(self, visible: bool) -> None:
        for widget in self._chat_hero_widgets:
            widget.setVisible(bool(visible))

    def _build_devices_page(self) -> QWidget:
        page, layout = self._page("Cihazlar", "Bağlı cihazları ve Remote durumunu izle.")
        self._devices_table.setColumnCount(3)
        self._devices_table.setHorizontalHeaderLabels(("Cihaz", "Durum", "Adres"))
        self._devices_table.setAlternatingRowColors(True)
        layout.addWidget(self._devices_table, 1)
        refresh = QPushButton("Cihazları yenile")
        refresh.clicked.connect(self._refresh_devices)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        return page

    def _build_now_playing_page(self) -> QWidget:
        page, layout = self._page("Now Playing", "Aktif medya oturumunu görüntüle.")
        self._now_playing_cover.setMinimumSize(180, 180)
        self._now_playing_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._now_playing_cover.setText("Kapak bekleniyor")
        layout.addWidget(self._now_playing_cover, alignment=Qt.AlignmentFlag.AlignCenter)
        box = QGroupBox("Şu an çalıyor")
        form = QFormLayout(box)
        for key, label in (
            ("title", "Parça"),
            ("artist", "Sanatçı"),
            ("app", "Kaynak"),
            ("playback_status", "Durum"),
        ):
            value = QLabel("Bekleniyor")
            self._now_playing_values[key] = value
            form.addRow(label, value)
        layout.addWidget(box)

        progress_row = QHBoxLayout()
        page_progress = QSlider(Qt.Orientation.Horizontal, page)
        page_progress.setObjectName("nowPlayingPageProgress")
        page_progress.setRange(0, 1000)
        page_progress.setValue(0)
        page_progress.sliderMoved.connect(self._preview_page_position)
        page_progress.sliderReleased.connect(self._set_now_playing_page_position)
        page_timeline = QLabel("00:00 / 00:00", page)
        page_timeline.setObjectName("nowPlayingPageTimeline")
        page_timeline.setMinimumWidth(120)
        page_timeline.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(page_progress, 1)
        progress_row.addWidget(page_timeline)
        layout.addLayout(progress_row)
        self._now_playing_page_progress = page_progress
        self._now_playing_page_timeline = page_timeline

        controls = QHBoxLayout()
        for action, text in (("previous", "Önceki"), ("play_pause", "Oynat / Duraklat"), ("next", "Sonraki")):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, value=action: self._media_action(value))
            controls.addWidget(button)
        layout.addLayout(controls)
        volume_row = QHBoxLayout()
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(50)
        self._volume_slider.setToolTip("Bilgisayar ses seviyesi")
        self._volume_slider.sliderReleased.connect(self._set_volume)
        self._mute_button.clicked.connect(self._toggle_mute)
        volume_row.addWidget(self._volume_label)
        volume_row.addWidget(self._volume_slider, 1)
        volume_row.addWidget(self._mute_button)
        layout.addLayout(volume_row)
        refresh = QPushButton("Medya bilgisini yenile")
        refresh.clicked.connect(self._refresh_now_playing)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        fullscreen = QPushButton("Tam ekran Now Playing")
        fullscreen.clicked.connect(self._open_now_playing_fullscreen)
        layout.addWidget(fullscreen, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _build_automations_page(self) -> QWidget:
        page, layout = self._page("Otomasyonlar", "Zamanlayıcıları ve çalışma akışlarını görüntüle.")
        self._automations_table.setColumnCount(3)
        self._automations_table.setHorizontalHeaderLabels(("Ad", "Aktif", "Tetikleyici"))
        self._automations_table.setAlternatingRowColors(True)
        layout.addWidget(self._automations_table, 1)
        refresh = QPushButton("Otomasyonları yenile")
        refresh.clicked.connect(self._refresh_automations)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        return page

    def _build_remote_page(self) -> QWidget:
        page, layout = self._page("Remote", "Bağlı telefon ve Termux cihazlarına güvenli komut gönder.")
        self._remote_output.setReadOnly(True)
        self._remote_output.setPlaceholderText("Remote sonuçları burada görünecek.")
        layout.addWidget(self._remote_output, 1)
        controls = QHBoxLayout()
        self._remote_input.setPlaceholderText("Örnek: telefondaki durumu söyle")
        self._remote_input.returnPressed.connect(self._submit_remote)
        send = QPushButton("Gönder")
        send.clicked.connect(self._submit_remote)
        controls.addWidget(self._remote_input, 1)
        controls.addWidget(send)
        layout.addLayout(controls)
        hint = QLabel("Cihaz bağlı değilse komut gönderilmez; sonuç bu alanda raporlanır.")
        layout.addWidget(hint)
        return page

    def _build_notifications_page(self) -> QWidget:
        page, layout = self._page("Bildirimler", "NetOps, telefon ve komut olaylarının canlı akışı.")
        layout.addWidget(self._notifications_list, 1)
        refresh = QPushButton("Bildirimleri yenile")
        refresh.clicked.connect(self._refresh_notifications)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        return page

    def _build_system_page(self) -> QWidget:
        page, layout = self._page("Sistem Durumu", "NetOps servisleri ve bilgisayar kaynakları.")
        box = QGroupBox("Durum")
        grid = QGridLayout(box)
        for row, key in enumerate(("cpu", "ram", "gpu", "devices", "remote")):
            value = QLabel("Ölçülüyor")
            self._system_values.setdefault(key, []).append(value)
            grid.addWidget(QLabel(key.upper()), row, 0)
            grid.addWidget(value, row, 1)
        layout.addWidget(box)
        refresh = QPushButton("Durumu yenile")
        refresh.clicked.connect(self._refresh_system)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page("Ayarlar", "Native NetOps arayüzünün davranışlarını yönet.")
        self._settings_tabs = QTabWidget()
        self._settings_tabs.setObjectName("settingsTabs")
        self._settings_tabs.setDocumentMode(True)
        self._settings_tabs.setUsesScrollButtons(False)
        self._settings_tabs.setMovable(False)
        self._settings_tabs.tabBar().setExpanding(False)
        self._settings_tabs.tabBar().setMinimumHeight(42)
        builders = (
            self._settings_general_tab,
            self._settings_system_tab,
            self._settings_appearance_tab,
            self._settings_window_tab,
            self._settings_netolab_tab,
            self._settings_security_tab,
            self._settings_updates_tab,
            self._settings_about_tab,
        )
        for title, builder in zip(native_settings_sections(), builders):
            self._settings_tabs.addTab(builder(), title)
        self._settings_tabs.currentChanged.connect(self._animate_settings_tab)
        layout.addWidget(self._settings_tabs, 1)
        actions = QHBoxLayout()
        apply_button = QPushButton("Ayarları kaydet")
        status = QLabel("Hazır")
        self._settings_status = status
        apply_button.clicked.connect(lambda: self._save_settings(status))
        actions.addWidget(apply_button)
        actions.addWidget(status)
        actions.addStretch(1)
        layout.addLayout(actions)
        return page

    def _finish_settings_tab_animation(self, index: int, animation: QPropertyAnimation) -> None:
        if self._settings_tab_animations.get(index) is animation:
            self._settings_tab_animations.pop(index, None)
        animation.deleteLater()

    def _animate_settings_tab(self, index: int) -> None:
        if self._settings_tabs is None:
            return
        previous = self._settings_tab_animations.get(int(index))
        if previous is not None:
            previous.stop()
            previous.deleteLater()
        # Do not attach graphics effects to QTabBar or its pages. Qt may
        # partially paint tab labels after a tab switch when an opacity effect
        # is active, leaving only the selected tab visible.
        self._settings_tabs.tabBar().setGraphicsEffect(None)
        self._settings_tab_animations.pop(int(index), None)

    def _animate_settings_surface(self) -> None:
        if self._settings_tabs is None:
            return
        if self._settings_animation is not None:
            self._settings_animation.stop()
            self._settings_animation.deleteLater()
        self._settings_animation = None
        # QTabWidget becomes intermittently blank on Windows while a graphics
        # effect is animating its internal stacked page. Keep the settings
        # surface fully renderable instead of fading the widget itself.
        self._settings_tabs.setGraphicsEffect(None)
        self._animate_settings_tab(self._settings_tabs.currentIndex())

    def _setting_checkbox(self, parent: QWidget, key: str, text: str, default: bool = False) -> QCheckBox:
        control = QCheckBox(text, parent)
        control.setChecked(bool(self._settings_data.get(key, default)))
        self._settings_controls[key] = control
        control.toggled.connect(lambda _checked, setting_key=key: self._schedule_settings_save(setting_key))
        return control

    def _setting_combo(self, parent: QWidget, key: str, values: tuple[tuple[str, Any], ...], default: Any) -> QComboBox:
        control = QComboBox(parent)
        for label, value in values:
            control.addItem(label, value)
        current = self._settings_data.get(key, default)
        index = control.findData(current)
        control.setCurrentIndex(index if index >= 0 else 0)
        self._settings_controls[key] = control
        if key == "dil":
            control.currentIndexChanged.connect(self._on_language_changed)
        control.currentIndexChanged.connect(lambda _index, setting_key=key: self._schedule_settings_save(setting_key))
        return control

    def _settings_tab(self, title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(title))
        layout.addWidget(QLabel(description))
        return page, layout

    def _settings_general_tab(self) -> QWidget:
        page, layout = self._settings_tab("Genel", "Dil ve temel NetOps davranışları.")
        layout.addWidget(QLabel("Uygulama dili"))
        layout.addWidget(self._setting_combo(page, "dil", (("Türkçe", "tr"), ("English", "en")), "tr"))
        layout.addWidget(self._setting_checkbox(page, "live_mode_otomatik_baslat", "Live Mode'u açılışta başlat"))
        layout.addWidget(self._setting_checkbox(page, "ogrenme_modu_acik", "Yerel öğrenme modunu etkinleştir"))
        layout.addWidget(self._setting_checkbox(page, "local_api_enabled", "Yerel API erişimine izin ver", True))
        layout.addStretch(1)
        return page

    def _settings_system_tab(self) -> QWidget:
        page, layout = self._settings_tab("Sistem", "Kaynak izleme ve arka plan servisleri.")
        layout.addWidget(QLabel("CPU/RAM ve servis durumu Sistem Durumu sekmesinden izlenir."))
        layout.addWidget(self._setting_checkbox(page, "background_services_enabled", "Arka plan servislerini etkinleştir", True))
        refresh = QPushButton("Sistem durumunu yenile")
        refresh.clicked.connect(self._refresh_system)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _settings_appearance_tab(self) -> QWidget:
        page, layout = self._settings_tab("Görünüm", "Tema, açılış animasyonu ve ses tercihleri.")
        layout.addWidget(QLabel("Tema"))
        layout.addWidget(self._setting_combo(page, "tema", (("Koyu", "dark"), ("Açık", "light")), "dark"))
        layout.addWidget(QLabel("Renk teması"))
        layout.addWidget(
            self._setting_combo(
                page,
                "renk_temasi",
                (("Yeşil", "green"), ("Mavi", "blue"), ("Koyu mavi", "dark-blue")),
                "blue",
            )
        )
        layout.addWidget(self._setting_checkbox(page, "startup_animation_enabled", "Açılış animasyonunu etkinleştir", True))
        layout.addWidget(self._setting_checkbox(page, "startup_sound_enabled", "Açılış sesini etkinleştir", True))
        gif_button = QPushButton("Açılış GIF'i seç")
        gif_button.clicked.connect(lambda: self._choose_setting_file("secilen_gif", "GIF (*.gif)"))
        sound_button = QPushButton("Açılış sesini seç")
        sound_button.clicked.connect(lambda: self._choose_setting_file("secilen_ses", "Ses (*.mp3 *.wav)"))
        layout.addWidget(gif_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(sound_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _settings_window_tab(self) -> QWidget:
        page, layout = self._settings_tab("Pencere Yöneticisi", "Native NetOps penceresinin açılış davranışı.")
        layout.addWidget(self._setting_checkbox(page, "netops_native_maximized", "Açılışta pencereyi büyüt", True))
        layout.addWidget(self._setting_checkbox(page, "now_playing_on_start", "Now Playing durumunu açılışta izle"))
        layout.addStretch(1)
        return page

    def _settings_netolab_tab(self) -> QWidget:
        page, layout = self._settings_tab("Netolab", "Yerel eklenti ve beceri altyapısı.")
        layout.addWidget(self._setting_checkbox(page, "netolab_enabled", "Yerel Netolab bileşenlerini etkinleştir", True))
        layout.addWidget(QLabel("Eklentiler kullanıcı onayı olmadan çalıştırılmaz."))
        layout.addStretch(1)
        return page

    def _settings_security_tab(self) -> QWidget:
        page, layout = self._settings_tab("Güvenlik", "Onaylar ve yerel erişim seçenekleri.")
        layout.addWidget(self._setting_checkbox(page, "risk_confirmation_required", "Riskli işlemlerde onay iste", True))
        layout.addWidget(self._setting_checkbox(page, "local_api_enabled", "Yerel API erişimine izin ver", True))
        layout.addStretch(1)
        return page

    def _settings_updates_tab(self) -> QWidget:
        page, layout = self._settings_tab("Güncellemeler", "NetOps sürüm ve güncelleme tercihleri.")
        layout.addWidget(self._setting_checkbox(page, "auto_update_check", "Açılışta güncellemeleri kontrol et"))
        status = QLabel("Yapılandırma")
        status.setWordWrap(True)
        check = QPushButton("Güncellemeleri kontrol et")
        check.clicked.connect(self._request_update_check)
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.hide()
        restart = QPushButton("Yeniden başlat")
        restart.clicked.connect(self._restart_after_update)
        restart.hide()
        self._update_check_button = check
        self._update_status_label = status
        self._update_progress = progress
        self._update_restart_button = restart
        layout.addWidget(check, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(status)
        layout.addWidget(progress)
        layout.addWidget(restart, alignment=Qt.AlignmentFlag.AlignLeft)

        center = QGroupBox("Güncelleme merkezi")
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel("Güncelleme geçmişi ve güvenli geri alma"))
        rollback_status = QLabel("Geri alma kontrol ediliyor...")
        rollback_status.setWordWrap(True)
        rollback_button = QPushButton("Son güncellemeyi geri al")
        rollback_button.setEnabled(False)
        rollback_button.clicked.connect(self._request_update_rollback)
        log_view = QPlainTextEdit()
        log_view.setReadOnly(True)
        log_view.setMaximumHeight(120)
        log_view.setPlainText("İşlem günlüğü burada görünür.")
        self._update_rollback_button = rollback_button
        self._update_rollback_status = rollback_status
        self._update_log_view = log_view
        center_layout.addWidget(rollback_status)
        center_layout.addWidget(rollback_button, alignment=Qt.AlignmentFlag.AlignLeft)
        center_layout.addWidget(log_view)
        layout.addWidget(center)
        layout.addStretch(1)
        QTimer.singleShot(0, self._refresh_update_center)
        return page

    def _request_update_check(self) -> None:
        if self._update_pending:
            return
        self._update_pending = True
        self._update_plan_path = ""
        if self._update_check_button is not None:
            self._update_check_button.setEnabled(False)
        if self._update_restart_button is not None:
            self._update_restart_button.hide()
            self._update_restart_button.setEnabled(False)
        if self._update_progress is not None:
            self._update_progress.hide()
            self._update_progress.setValue(0)
        if self._update_status_label is not None:
            self._update_status_label.setText(self._t("Güncellemeler kontrol ediliyor..."))

        def worker() -> None:
            try:
                from neto_updater import check_for_updates

                result = check_for_updates(force=True)
            except Exception as exc:
                result = {"ok": False, "available": False, "message": str(exc), "error": str(exc)}
            self._update_queue.put(("check", result))

        threading.Thread(target=worker, name="NetOpsUpdateCheck", daemon=True).start()

    def _poll_update_queue(self) -> None:
        while True:
            try:
                event, payload = self._update_queue.get_nowait()
            except Empty:
                return
            if event == "check":
                self._handle_update_check_result(payload)
            elif event == "progress":
                index, total = payload
                self._handle_update_progress(index, total)
            elif event == "downloaded":
                self._handle_update_downloaded(str(payload))
            elif event == "installed":
                self._handle_update_installed(payload)
            elif event == "rollback_installed":
                self._handle_rollback_installed(payload)
            elif event == "rollback_error":
                self._handle_rollback_error(str(payload))
            elif event == "error":
                self._handle_update_error(str(payload))

    def _ask_update_confirmation(self, update: dict[str, Any]) -> bool:
        version = str(update.get("latest_version") or update.get("tag_name") or "yeni sürüm")
        message = (
            f"NetOps {version} için güncelleme bulundu.\n\n"
            "Güncellemeyi yapılandırmak ister misiniz?"
        )
        answer = QMessageBox.question(
            self,
            self._t("Güncelleme onayı"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _handle_update_check_result(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("ok", False):
            self._update_pending = False
            if self._update_check_button is not None:
                self._update_check_button.setEnabled(True)
            if self._update_status_label is not None:
                self._update_status_label.setText(self._t("Güncelleme kontrolü başarısız"))
            return
        if not result.get("available"):
            self._update_pending = False
            if self._update_check_button is not None:
                self._update_check_button.setEnabled(True)
            if self._update_status_label is not None:
                self._update_status_label.setText(self._t("Sistem güncel"))
            return
        if not self._ask_update_confirmation(result):
            self._update_pending = False
            if self._update_check_button is not None:
                self._update_check_button.setEnabled(True)
            if self._update_status_label is not None:
                self._update_status_label.setText(self._t("Güncelleme iptal edildi"))
            return
        self._start_update_download(result)

    def _start_update_download(self, update: dict[str, Any]) -> None:
        if self._update_status_label is not None:
            self._update_status_label.setText(self._t("Güncelleme yapılandırılıyor..."))
        if self._update_progress is not None:
            self._update_progress.setRange(0, 100)
            self._update_progress.setValue(0)
            self._update_progress.show()
        if self._update_restart_button is not None:
            self._update_restart_button.hide()
        if self._update_check_button is not None:
            self._update_check_button.setEnabled(False)

        def progress_callback(index: int, total: int) -> None:
            self._update_queue.put(("progress", (index, total)))

        def worker() -> None:
            try:
                from neto_system_updater import download_files

                plan_path = download_files(update, progress_callback=progress_callback)
                self._update_queue.put(("downloaded", plan_path))
            except Exception as exc:
                self._update_queue.put(("error", str(exc)))

        threading.Thread(target=worker, name="NetOpsUpdateDownload", daemon=True).start()

    def _handle_update_progress(self, index: int, total: int) -> None:
        total = max(int(total), 1)
        index = min(max(int(index), 0), total)
        if self._update_progress is not None:
            self._update_progress.setRange(0, total)
            self._update_progress.setValue(index)
        if self._update_status_label is not None:
            percent = int((index / total) * 100)
            self._update_status_label.setText(
                f"{self._t('Güncelleme yapılandırılıyor...')} %{percent}"
            )

    def _handle_update_downloaded(self, plan_path: str) -> None:
        self._update_pending = False
        self._update_plan_path = plan_path
        if self._update_progress is not None:
            self._update_progress.setValue(self._update_progress.maximum())
            self._update_progress.show()
        if self._update_status_label is not None:
            self._update_status_label.setText(self._t("Güncelleme yapılandırıldı"))
        if self._update_check_button is not None:
            self._update_check_button.setEnabled(False)
        if self._update_restart_button is not None:
            self._update_restart_button.setEnabled(True)
            self._update_restart_button.show()

    def _handle_update_error(self, message: str) -> None:
        self._update_pending = False
        self._update_plan_path = ""
        self._hide_update_loading_screen()
        if self._update_check_button is not None:
            self._update_check_button.setEnabled(True)
        if self._update_progress is not None:
            self._update_progress.hide()
        if self._update_restart_button is not None:
            self._update_restart_button.hide()
        if self._update_status_label is not None:
            detail = message.strip()
            self._update_status_label.setText(
                f"{self._t('Güncelleme başarısız')}: {detail}" if detail else self._t("Güncelleme başarısız")
            )

    def _restart_after_update(self) -> None:
        if self._update_pending or not self._update_plan_path:
            return
        plan_path = self._update_plan_path
        self._update_pending = True
        self._update_exit_requested = False
        self._show_update_loading_screen()
        if self._update_restart_button is not None:
            self._update_restart_button.setEnabled(False)
        if self._update_status_label is not None:
            self._update_status_label.setText(self._t("Yeniden başlatılıyor..."))

        def worker() -> None:
            try:
                from neto_system_updater import install_downloaded

                result = install_downloaded(plan_path, restart=True)
                self._update_queue.put(("installed", result))
            except Exception as exc:
                self._update_queue.put(("error", str(exc)))

        threading.Thread(target=worker, name="NetOpsUpdateInstall", daemon=True).start()

    def _handle_update_installed(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("ok"):
            self._handle_update_error(str((result or {}).get("error") if isinstance(result, dict) else result))
            return
        self._update_pending = False
        self._update_exit_requested = True
        if self._update_loading_progress is not None:
            self._update_loading_progress.setValue(100)
        if self._update_loading_label is not None:
            self._update_loading_label.setText(self._t("Güncelleme yüklendi"))
        QTimer.singleShot(650, self.close)

    def _append_update_log(self, message: str) -> None:
        if self._update_log_view is None:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        current = self._update_log_view.toPlainText().strip()
        if current == self._t("İşlem günlüğü burada görünür."):
            current = ""
        lines = [line for line in current.splitlines() if line.strip()]
        lines.append(f"[{stamp}] {message}")
        self._update_log_view.setPlainText("\n".join(lines[-8:]))
        self._update_log_view.verticalScrollBar().setValue(
            self._update_log_view.verticalScrollBar().maximum()
        )

    def _refresh_update_center(self) -> None:
        if self._update_rollback_status is None or self._update_rollback_button is None:
            return
        try:
            import neto_system_updater

            record = neto_system_updater.latest_rollback()
        except Exception as exc:
            self._update_rollback_record = None
            self._update_rollback_button.setEnabled(False)
            self._update_rollback_status.setText(self._t("Geri alma kaydı yok"))
            self._append_update_log(f"{self._t('Geri alma başarısız')}: {exc}")
            return
        self._update_rollback_record = record if isinstance(record, dict) else None
        if self._update_rollback_record is None:
            self._update_rollback_button.setEnabled(False)
            self._update_rollback_status.setText(self._t("Geri alma kaydı yok"))
            self._append_update_log(self._t("Geri alma kaydı yok"))
            return
        version = str(
            self._update_rollback_record.get("version")
            or self._update_rollback_record.get("release_tag")
            or "Bilinmiyor"
        )
        try:
            created = datetime.fromtimestamp(
                float(self._update_rollback_record.get("created_at") or 0)
            ).strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError, OSError):
            created = ""
        suffix = f" • {created}" if created else ""
        self._update_rollback_button.setEnabled(not self._update_pending)
        self._update_rollback_status.setText(f"{self._t('Geri alma kaydı')}: {version}{suffix}")
        self._append_update_log(f"{self._t('Geri alma kaydı')}: {version}")

    def _request_update_rollback(self) -> None:
        record = self._update_rollback_record
        if self._update_pending or not isinstance(record, dict):
            return
        answer = QMessageBox.question(
            self,
            self._t("Geri alma onayı"),
            self._t("Son güncellemenin güvenli yedeğine dönmek istiyor musunuz?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._append_update_log(self._t("Güncelleme iptal edildi"))
            return
        self._update_pending = True
        self._update_exit_requested = False
        self._show_update_loading_screen()
        if self._update_loading_label is not None:
            self._update_loading_label.setText(self._t("Geri alma hazırlanıyor..."))
        if self._update_rollback_status is not None:
            self._update_rollback_status.setText(self._t("Geri alma hazırlanıyor..."))
        if self._update_rollback_button is not None:
            self._update_rollback_button.setEnabled(False)
        self._append_update_log(self._t("Geri alma hazırlanıyor..."))

        def worker() -> None:
            try:
                from neto_update_helper import install_rollback_update

                result = install_rollback_update(record, restart=True)
                self._update_queue.put(("rollback_installed", result))
            except Exception as exc:
                self._update_queue.put(("rollback_error", str(exc)))

        threading.Thread(target=worker, name="NetOpsRollbackInstall", daemon=True).start()

    def _handle_rollback_installed(self, result: Any) -> None:
        if not isinstance(result, dict) or not result.get("ok"):
            self._update_pending = False
            self._hide_update_loading_screen()
            if self._update_rollback_button is not None:
                self._update_rollback_button.setEnabled(True)
            if self._update_rollback_status is not None:
                self._update_rollback_status.setText(self._t("Geri alma başarısız"))
            self._append_update_log(self._t("Geri alma başarısız"))
            return
        self._update_pending = False
        self._update_exit_requested = True
        if self._update_loading_progress is not None:
            self._update_loading_progress.setValue(100)
        if self._update_loading_label is not None:
            self._update_loading_label.setText(self._t("Geri alma hazırlandı"))
        self._append_update_log(self._t("Geri alma hazırlandı"))
        QTimer.singleShot(650, self.close)

    def _handle_rollback_error(self, message: str) -> None:
        self._update_pending = False
        self._hide_update_loading_screen()
        if self._update_rollback_button is not None:
            self._update_rollback_button.setEnabled(True)
        if self._update_rollback_status is not None:
            self._update_rollback_status.setText(self._t("Geri alma başarısız"))
        detail = message.strip()
        self._append_update_log(
            f"{self._t('Geri alma başarısız')}: {detail}" if detail else self._t("Geri alma başarısız")
        )

    def _show_update_loading_screen(self) -> None:
        root = self._netops_root or self.centralWidget()
        if root is None:
            return
        if self._update_loading_overlay is None:
            overlay = QFrame(root)
            overlay.setObjectName("updateLoadingOverlay")
            overlay.setStyleSheet(
                "QFrame#updateLoadingOverlay { background: rgba(5, 7, 11, 245); }"
                "QLabel#updateLoadingTitle { color: #f4f7fb; font-size: 22px; font-weight: 700; }"
                "QLabel#updateLoadingDetail { color: #aeb8c8; font-size: 13px; }"
                "QProgressBar#updateLoadingProgress { background: #151b27; border: 1px solid #2d405f; border-radius: 6px; height: 10px; }"
                "QProgressBar#updateLoadingProgress::chunk { background: #6f91d9; border-radius: 5px; }"
            )
            layout = QVBoxLayout(overlay)
            layout.setContentsMargins(32, 32, 32, 32)
            layout.setSpacing(12)
            layout.addStretch(1)
            title = QLabel(self._t("Güncelleme yükleniyor..."), overlay)
            title.setObjectName("updateLoadingTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail = QLabel("NetOps güvenli güncelleme hazırlanıyor", overlay)
            detail.setObjectName("updateLoadingDetail")
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            progress = QProgressBar(overlay)
            progress.setObjectName("updateLoadingProgress")
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(False)
            progress.setMaximumWidth(520)
            layout.addWidget(title)
            layout.addWidget(detail)
            layout.addWidget(progress, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addStretch(1)
            self._update_loading_overlay = overlay
            self._update_loading_label = title
            self._update_loading_progress = progress
        else:
            self._update_loading_label.setText(self._t("Güncelleme yükleniyor..."))
            self._update_loading_progress.setValue(0)
        self._update_loading_overlay.setGeometry(root.rect())
        self._update_loading_overlay.raise_()
        self._update_loading_overlay.show()

    def _hide_update_loading_screen(self) -> None:
        if self._update_loading_overlay is not None:
            self._update_loading_overlay.hide()

    def _settings_about_tab(self) -> QWidget:
        page, layout = self._settings_tab("Hakkında", "NetOps native masaüstü arayüzü.")
        layout.addWidget(QLabel("NetOps v1.53.1"))
        layout.addWidget(QLabel("PySide6 Qt Widgets tabanı"))
        layout.addWidget(QLabel(str(Path(__file__).resolve().parent)))
        layout.addStretch(1)
        return page

    def _choose_setting_file(self, key: str, pattern: str) -> None:
        path, _selected = QFileDialog.getOpenFileName(self, "Dosya seç", "", pattern)
        if path:
            self._settings_data[key] = path
            self._schedule_settings_save(key)

    def _schedule_settings_save(self, _key: str = "") -> None:
        if self._settings_controls:
            self._settings_save_timer.start()

    def _auto_save_settings(self) -> None:
        self._save_settings(self._settings_status, automatic=True)

    def _save_settings(self, status: QLabel | None = None, *, automatic: bool = False) -> None:
        for key, control in self._settings_controls.items():
            if isinstance(control, QCheckBox):
                self._settings_data[key] = control.isChecked()
            elif isinstance(control, QComboBox):
                self._settings_data[key] = control.currentData()
        result = self.backend.run("save_settings", self._settings_data)
        failed = isinstance(result, dict) and result.get("ok") is False
        if not failed:
            self._native_palette = native_theme_palette(self._settings_data)
            self._apply_native_visuals()
            self._set_language(self._settings_data.get("dil", self._language))
        if status is not None:
            message = "Otomatik kaydedildi" if automatic and not failed else "Ayarlar kaydedildi"
            status.setText(self._t(message) if not failed else _display(result))

    def _set_language(self, language: Any) -> None:
        self._language = self._normalize_language(language)
        self._settings_data["dil"] = self._language
        self._apply_language()

    def closeEvent(self, event) -> None:
        if self._update_pending and not self._update_exit_requested:
            if self._update_status_label is not None:
                self._update_status_label.setText(self._t("Kapatılamıyor: güncelleme devam ediyor"))
            event.ignore()
            return
        self._chat_response_timer.stop()
        self._update_timer.stop()
        if self._settings_save_timer.isActive():
            self._settings_save_timer.stop()
            self._auto_save_settings()
        super().closeEvent(event)

    def _apply_settings(self, maximized: bool, reduce_motion: bool, status: QLabel) -> None:
        if reduce_motion:
            os.environ["NETOPS_REDUCE_MOTION"] = "1"
        else:
            os.environ.pop("NETOPS_REDUCE_MOTION", None)
        if maximized:
            self.showMaximized()
        else:
            self.showNormal()
        status.setText("Ayarlar uygulandı")

    def _animate_button_feedback(self, button: QPushButton) -> None:
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return
        effect = button.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(button)
            button.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(native_visual_contract()["button_feedback_ms"])
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._button_feedback_animations[id(button)] = animation

    def _animate_navigation_focus(self, button: QPushButton) -> None:
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return
        effect = button.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(button)
            button.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(native_visual_contract()["button_feedback_ms"])
        animation.setStartValue(0.84)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._navigation_animations[id(button)] = animation

    def _submit_chat(self) -> None:
        text = self._chat_input.text().strip()
        if not text or self._chat_pending:
            return
        self._remember_recent_chat(text)
        self._set_chat_hero_visible(False)
        self._chat_output.append_message(text, "user")
        self._chat_output.show_typing()
        self._chat_input.clear()
        self._chat_pending = True
        self._chat_input.setEnabled(False)
        if self._chat_send_button is not None:
            self._chat_send_button.setEnabled(False)
        threading.Thread(
            target=self._run_chat_request,
            args=(text,),
            daemon=True,
            name="netops-chat-request",
        ).start()

    def _start_ai_plan(self) -> None:
        """Focus chat on the local multi-step task planner."""
        self._open_native_page("chat")
        self._chat_input.setPlaceholderText(self._t("Örnek: RAM'i göster sonra müziği durdur"))
        self._chat_input.setFocus()
        if self._sidebar_plan_status is not None:
            self._sidebar_plan_status.setText(self._t("Plan örneği hazırlandı"))
        self._status.setText(self._t("AI görev planı hazır"))

    def _run_chat_request(self, text: str) -> None:
        result = self.backend.run("chat", text)
        self._chat_response_queue.put((text, result))

    def _poll_chat_response(self) -> None:
        if not self._chat_pending:
            return
        try:
            _submitted_text, result = self._chat_response_queue.get_nowait()
        except Empty:
            return
        reply = _display(result)
        self._chat_output.hide_typing()
        self._chat_output.append_message(reply, "assistant")
        self._chat_pending = False
        self._chat_input.setEnabled(True)
        self._chat_input.setFocus()
        if self._chat_send_button is not None:
            self._chat_send_button.setEnabled(True)
        # Text must remain available even when the optional local TTS is absent.
        # Run speech outside the Qt event loop so a voice model never freezes UI.
        if not (isinstance(result, dict) and result.get("error")) and reply:
            threading.Thread(
                target=lambda: self.backend.run("speech", reply),
                daemon=True,
                name="netops-chat-speech",
            ).start()

    def _open_native_page(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        if key == "chat":
            self._collapse_compact_controls()
        if not self._history_navigation:
            self._page_history = self._page_history[: self._page_history_index + 1]
            if not self._page_history or self._page_history[-1] != key:
                self._page_history.append(key)
            self._page_history_index = len(self._page_history) - 1
        if self._page_stack.currentWidget() is page:
            if key == "now_playing":
                self._refresh_volume()
            elif key == "settings":
                self._animate_settings_surface()
            return
        self._page_stack.setCurrentWidget(page)
        if key == "now_playing":
            self._refresh_volume()
        elif key == "settings":
            self._animate_settings_surface()
        for route, button in self._nav_buttons.items():
            button.setChecked(route == key)
            if route == key:
                self._animate_navigation_focus(button)
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        self._page_effect = effect
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(int(native_motion_contract()["page_ms"]))
        animation.setStartValue(0.82)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._page_animation = animation

    def _submit_remote(self) -> None:
        text = self._remote_input.text().strip()
        if not text:
            return
        result = self.backend.run("remote", text)
        self._remote_output.appendPlainText(f"> {text}\n{_display(result)}\n")
        self._remote_input.clear()

    def _refresh_notifications(self) -> None:
        result = self.backend.run("notifications")
        events = result if isinstance(result, list) else []
        self._update_sidebar_notification_badge(len(events))
        self._refresh_sidebar_activity(events)
        self._notifications_list.clear()
        if not events:
            self._notifications_list.addItem(self._t("Yeni bildirim yok."))
            return
        for event in reversed(events[-50:]):
            event = event if isinstance(event, dict) else {}
            timestamp = str(event.get("at", ""))
            source = str(event.get("source", "NetOps"))
            message = str(event.get("message", event.get("detail", "")))
            command = str(event.get("command", event.get("title", self._t("Olay"))))
            self._notifications_list.addItem(f"[{timestamp}] {source} • {command}\n{message}")

    def _update_sidebar_notification_badge(self, count: int) -> None:
        self._sidebar_notification_count = max(0, int(count or 0))
        if self._sidebar_notification_button is not None:
            self._sidebar_notification_button.setText(
                f"{self._t('Bildirimler')}  •  {self._sidebar_notification_count}"
            )

    def _refresh_sidebar_activity(self, events: list[Any]) -> None:
        if self._sidebar_activity_list is None:
            return
        self._sidebar_activity_list.clear()
        if not events:
            self._sidebar_activity_list.addItem(self._t("Son işlem yok."))
            return
        for event in reversed(events[-3:]):
            event = event if isinstance(event, dict) else {}
            title = str(event.get("title", event.get("command", self._t("Olay"))))
            message = str(event.get("message", event.get("detail", ""))).strip()
            short_message = message if len(message) <= 42 else message[:39] + "..."
            item = QListWidgetItem(f"{title}: {short_message}" if short_message else title)
            item.setToolTip(message or title)
            self._sidebar_activity_list.addItem(item)

    def _refresh_system(self) -> None:
        snapshot = self.backend.snapshot()
        for key, labels in self._system_values.items():
            for label in labels:
                label.setText(self._t(snapshot.get(key, "Bilinmiyor")))
        self._refresh_sidebar_summary(snapshot)
        self._status.setText(self._t("Hazır" if not snapshot.get("error") else "Servis hatası"))

    def _refresh_sidebar_summary(self, snapshot: Any = None) -> None:
        if not isinstance(snapshot, dict):
            snapshot = self.backend.snapshot()
        if self._sidebar_devices_value is not None:
            self._sidebar_devices_value.setText(str(snapshot.get("devices", 0)))
        if self._sidebar_remote_value is not None:
            self._sidebar_remote_value.setText(self._t(snapshot.get("remote", "Hazır")))

    def _refresh_devices(self) -> None:
        result = self.backend.run("devices")
        devices = result.get("devices", []) if isinstance(result, dict) else result
        devices = devices if isinstance(devices, list) else []
        self._devices_table.setRowCount(len(devices))
        for row, device in enumerate(devices):
            device = device if isinstance(device, dict) else {}
            name = device.get("display_name", device.get("device_id", "Bilinmiyor"))
            state = "Çevrimiçi" if device.get("online") else "Çevrimdışı"
            self._devices_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self._devices_table.setItem(row, 1, QTableWidgetItem(self._t(state)))
            self._devices_table.setItem(row, 2, QTableWidgetItem(str(device.get("ip", ""))))

    def _refresh_now_playing(self) -> None:
        result = self.backend.run("now_playing")
        result = result if isinstance(result, dict) else {}
        raw_title = str(result.get("title", "Müzik bekleniyor") or "Müzik bekleniyor")
        title = self._t(raw_title)
        artist = str(result.get("artist", "") or "").strip()
        album = str(result.get("album", "") or "").strip()
        platform = str(result.get("app", result.get("source", "")) or "").strip()
        for key, label in self._now_playing_values.items():
            label.setText(self._t(result.get(key, "Bekleniyor") or "Bekleniyor"))

        compact_title = self._now_playing_compact_title
        compact_detail = self._now_playing_compact_detail
        compact_album = self._now_playing_compact_album
        compact_progress = self._now_playing_compact_progress
        compact_timeline = self._now_playing_compact_timeline
        compact_cover = self._now_playing_compact_cover
        if compact_title is not None:
            compact_title.setText(title)
        if compact_detail is not None:
            if raw_title != "Müzik bekleniyor":
                compact_detail.setText(
                    f"{artist or self._t('Bilinmiyor')} • {platform or self._t('Bilinmiyor')}"
                )
            else:
                compact_detail.setText(self._t("Kaynak bilgisi yok"))
        if compact_album is not None:
            compact_album.setText(album or self._t("Albüm: bekleniyor"))

        cover_path = str(result.get("cover_path", "") or "")
        track_key = "|".join((raw_title, artist, album, platform, cover_path))
        track_changed = track_key != self._now_playing_compact_track_key
        self._now_playing_compact_track_key = track_key
        if cover_path and Path(cover_path).exists():
            pixmap = load_cover_pixmap(cover_path)
            if not pixmap.isNull():
                self._now_playing_cover.setPixmap(
                    pixmap.scaled(
                        220,
                        220,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self._now_playing_cover.setText("")
                if compact_cover is not None:
                    compact_cover.set_art(pixmap, animate=track_changed)
        else:
            self._now_playing_cover.setPixmap(QPixmap())
            self._now_playing_cover.setText(self._t("Kapak bekleniyor"))
            if compact_cover is not None:
                compact_cover.clear_art("♪")

        try:
            position = max(0.0, float(result.get("position_seconds", 0) or 0))
            duration = max(0.0, float(result.get("duration_seconds", 0) or 0))
        except (TypeError, ValueError):
            position, duration = 0.0, 0.0
        self._now_playing_compact_duration = duration
        if compact_progress is not None:
            compact_progress.setEnabled(duration > 0)
        self._update_compact_timeline(position, duration, update_slider=True)
        self._update_now_playing_page_timeline(position, duration, update_slider=True)
        if self._now_playing_compact_expanded:
            self._refresh_compact_volume()
        island_text = self._t("♪  Müzik bekleniyor") if not artist and raw_title == "Müzik bekleniyor" else "♪  " + " • ".join(item for item in (title, artist) if item)
        self._update_now_playing_island(island_text)

    @staticmethod
    def _format_media_time(seconds: float) -> str:
        total = max(0, int(seconds))
        return f"{total // 60:02d}:{total % 60:02d}"

    def _update_compact_timeline(self, position: float, duration: float, *, update_slider: bool) -> None:
        progress = self._now_playing_compact_progress
        timeline = self._now_playing_compact_timeline
        if progress is None or timeline is None:
            return
        if duration <= 0:
            if update_slider:
                progress.blockSignals(True)
                progress.setValue(0)
                progress.blockSignals(False)
            timeline.setText(self._t("Süre bilgisi bekleniyor"))
            return
        position = max(0.0, min(float(position), duration))
        if update_slider:
            progress.blockSignals(True)
            progress.setValue(max(0, min(1000, int((position / duration) * 1000))))
            progress.blockSignals(False)
        timeline.setText(f"{self._format_media_time(position)} / {self._format_media_time(duration)}")

    def _preview_compact_position(self, value: int) -> None:
        duration = self._now_playing_compact_duration
        if duration <= 0:
            return
        self._update_compact_timeline((int(value) / 1000.0) * duration, duration, update_slider=False)

    def _set_compact_position(self) -> None:
        progress = self._now_playing_compact_progress
        duration = self._now_playing_compact_duration
        if progress is None or duration <= 0:
            return
        position = (progress.value() / 1000.0) * duration
        self.backend.run("media_control", f"seek:{position:.2f}")
        QTimer.singleShot(250, self._refresh_now_playing)

    def _update_now_playing_page_timeline(self, position: float, duration: float, *, update_slider: bool) -> None:
        progress = self._now_playing_page_progress
        timeline = self._now_playing_page_timeline
        if progress is None or timeline is None:
            return
        self._now_playing_page_duration = max(0.0, float(duration))
        if duration <= 0:
            if update_slider:
                progress.blockSignals(True)
                progress.setValue(0)
                progress.blockSignals(False)
            progress.setEnabled(False)
            timeline.setText(self._t("Süre bilgisi bekleniyor"))
            return
        position = max(0.0, min(float(position), float(duration)))
        progress.setEnabled(True)
        if update_slider:
            progress.blockSignals(True)
            progress.setValue(max(0, min(1000, int((position / duration) * 1000))))
            progress.blockSignals(False)
        timeline.setText(f"{self._format_media_time(position)} / {self._format_media_time(duration)}")

    def _preview_page_position(self, value: int) -> None:
        duration = self._now_playing_page_duration
        if duration <= 0:
            return
        progress = self._now_playing_page_progress
        timeline = self._now_playing_page_timeline
        if progress is None or timeline is None:
            return
        position = (int(value) / 1000.0) * duration
        timeline.setText(f"{self._format_media_time(position)} / {self._format_media_time(duration)}")

    def _set_now_playing_page_position(self) -> None:
        progress = self._now_playing_page_progress
        duration = self._now_playing_page_duration
        if progress is None or duration <= 0:
            return
        position = (progress.value() / 1000.0) * duration
        self.backend.run("media_control", f"seek:{position:.2f}")
        QTimer.singleShot(250, self._refresh_now_playing)

    def _finish_compact_controls_animation(
        self,
        animation: QParallelAnimationGroup,
        expanded: bool,
    ) -> None:
        if self._now_playing_compact_expand_animation is not animation:
            return
        self._now_playing_compact_expand_animation = None
        controls = self._now_playing_compact_controls
        info = self._now_playing_compact_info
        card = self._now_playing_card
        if controls is not None and not expanded:
            controls.hide()
        if info is not None and not expanded:
            info.hide()
        if card is not None:
            card.setProperty("compact", not expanded)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
        animation.deleteLater()

    def _toggle_compact_controls(self) -> None:
        self._set_compact_controls(not self._now_playing_compact_expanded)

    def _collapse_compact_controls(self) -> None:
        if self._now_playing_compact_expanded:
            self._set_compact_controls(False)

    def _set_compact_controls(self, expanded: bool) -> None:
        card = self._now_playing_card
        info = self._now_playing_compact_info
        controls = self._now_playing_compact_controls
        cover = self._now_playing_compact_cover
        if card is None or info is None or controls is None:
            return
        expanded = bool(expanded)
        if expanded == self._now_playing_compact_expanded:
            return
        self._now_playing_compact_expanded = expanded
        if self._now_playing_compact_expand_animation is not None:
            self._now_playing_compact_expand_animation.stop()
            self._now_playing_compact_expand_animation.deleteLater()
            self._now_playing_compact_expand_animation = None
        if expanded:
            info.show()
            controls.show()
            if cover is not None:
                cover.set_compact_circle(False)
            card.setProperty("compact", False)
            self._refresh_compact_volume()
        else:
            info.hide()
            controls.hide()
            if cover is not None:
                cover.set_compact_circle(True)
            card.setProperty("compact", True)

        target_width = 720 if expanded else 76
        target_height = 176 if expanded else 76
        reduced_motion = os.environ.get("NETOPS_REDUCE_MOTION") == "1"
        if reduced_motion:
            card.setMinimumSize(target_width, target_height)
            card.setMaximumSize(target_width, target_height)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()
            return

        current_width = max(1, card.width() or card.minimumWidth())
        current_height = max(1, card.height() or card.minimumHeight())
        card.setMinimumWidth(current_width)
        card.setMaximumWidth(current_width)
        card.setMinimumHeight(current_height)
        card.setMaximumHeight(current_height)
        animation = QParallelAnimationGroup(self)
        for property_name, start_value, end_value in (
            (b"minimumWidth", current_width, target_width),
            (b"maximumWidth", current_width, target_width),
            (b"minimumHeight", current_height, target_height),
            (b"maximumHeight", current_height, target_height),
        ):
            size_animation = QPropertyAnimation(card, property_name, animation)
            size_animation.setStartValue(start_value)
            size_animation.setEndValue(end_value)
            size_animation.setDuration(180)
            size_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.addAnimation(size_animation)
        animation.finished.connect(
            lambda: self._finish_compact_controls_animation(animation, expanded)
        )
        self._now_playing_compact_expand_animation = animation
        animation.start()

    def _refresh_compact_volume(self) -> None:
        slider = self._now_playing_compact_volume
        mute = self._now_playing_compact_mute
        value_label = self._now_playing_compact_volume_value
        if slider is None:
            return
        result = self.backend.run("media_control", "volume_get")
        if not isinstance(result, dict) or result.get("value") is None:
            if value_label is not None:
                value_label.setText("—")
            return
        try:
            value = max(0, min(100, int(float(result["value"]))))
        except (TypeError, ValueError):
            if value_label is not None:
                value_label.setText("—")
            return
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)
        if value_label is not None:
            value_label.setText(f"%{value}")
        if mute is not None:
            mute.setText(self._t("Sesi aç" if result.get("muted") is True else "Sessize al"))

    def _set_compact_volume(self) -> None:
        slider = self._now_playing_compact_volume
        if slider is None:
            return
        value = slider.value()
        if self._now_playing_compact_volume_value is not None:
            self._now_playing_compact_volume_value.setText(f"%{value}")
        self.backend.run("media_control", f"volume_set:{value}")
        QTimer.singleShot(250, self._refresh_compact_volume)

    def _toggle_compact_mute(self) -> None:
        result = self.backend.run("media_control", "mute_toggle")
        if self._now_playing_compact_mute is not None and isinstance(result, dict):
            self._now_playing_compact_mute.setText(
                self._t("Sesi aç" if result.get("muted") is True else "Sessize al")
            )

    def _update_now_playing_island(self, text: str) -> None:
        text = str(text or self._t("♪  Müzik bekleniyor"))
        if text == self._now_playing_island_text:
            return
        self._now_playing_island_text = text
        self._now_playing_island.setText(text)
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            return
        effect = QGraphicsOpacityEffect(self._now_playing_island)
        effect.setOpacity(0.55)
        self._now_playing_island.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(native_visual_contract()["button_feedback_ms"])
        animation.setStartValue(0.55)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._now_playing_island_animation = animation

    def _set_volume(self) -> None:
        value = self._volume_slider.value()
        result = self.backend.run("media_control", f"volume_set:{value}")
        if isinstance(result, dict) and result.get("ok") is False:
            self._volume_label.setText(self._t("Ses: ayarlanamadı"))
        else:
            self._volume_label.setText(f"{self._t('Ses')}: %{value}")

    def _refresh_volume(self) -> None:
        result = self.backend.run("media_control", "volume_get")
        if not isinstance(result, dict) or result.get("value") is None:
            self._volume_label.setText(self._t("Ses: okunamadı"))
            return
        try:
            value = max(0, min(100, int(float(result["value"]))))
        except (TypeError, ValueError):
            self._volume_label.setText(self._t("Ses: okunamadı"))
            return
        self._volume_slider.blockSignals(True)
        self._volume_slider.setValue(value)
        self._volume_slider.blockSignals(False)
        muted = result.get("muted") is True
        self._volume_label.setText(f"{self._t('Ses')}: %{value}" + (f" • {self._t('Sessiz')}" if muted else ""))
        self._mute_button.setText(self._t("Sesi aç" if muted else "Sessize al"))

    def _toggle_mute(self) -> None:
        result = self.backend.run("media_control", "mute_toggle")
        muted = isinstance(result, dict) and result.get("muted") is True
        self._mute_button.setText(self._t("Sesi aç" if muted else "Sessize al"))

    def _open_now_playing_fullscreen(self) -> None:
        if self._now_playing_overlay is not None and self._now_playing_overlay.isVisible():
            self._now_playing_overlay.raise_()
            self._now_playing_overlay.activateWindow()
            return

        overlay = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        overlay.setObjectName("nowPlayingOverlay")
        overlay.setStyleSheet(
            "QWidget#nowPlayingOverlay { background: #05070b; color: #f4f7fb; }"
            "QLabel#nowPlayingHeading { color: #8fb4ff; letter-spacing: 3px; }"
            "QLabel#nowPlayingOverlayTitle { color: #ffffff; }"
            "QLabel#nowPlayingOverlayMeta { color: #aeb8c8; }"
            "QLabel#nowPlayingOverlayStatus { color: #79879d; }"
            "QLabel#nowPlayingOverlayClock { color: #ffffff; }"
            "QLabel#nowPlayingOverlayDate { color: #aeb8c8; }"
            "QProgressBar#nowPlayingOverlayProgress { background: #151b27; border: 1px solid #2d405f; border-radius: 5px; height: 8px; }"
            "QProgressBar#nowPlayingOverlayProgress::chunk { background: #6f91d9; border-radius: 5px; }"
            "QPushButton#nowPlayingControlButton, QPushButton#nowPlayingCloseButton { background: #101521; color: #f4f7fb; border: 1px solid #2d405f; border-radius: 18px; min-width: 48px; min-height: 42px; padding: 0; }"
            "QPushButton#nowPlayingControlButton:hover, QPushButton#nowPlayingCloseButton:hover { background: #1b2a43; border-color: #6f91d9; }"
            "QPushButton#nowPlayingControlButton:pressed, QPushButton#nowPlayingCloseButton:pressed { background: #2b4166; }"
        )
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(48, 26, 48, 24)
        layout.setSpacing(6)
        layout.addStretch(1)

        heading = QLabel()
        heading.setObjectName("nowPlayingHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 16px; font-weight: 700; letter-spacing: 3px;")
        layout.addWidget(heading)

        screen = QApplication.primaryScreen()
        screen_height = screen.availableGeometry().height() if screen is not None else 720
        cover_size = max(170, min(280, int(screen_height * 0.36)))
        cover = NowPlayingCover()
        cover.setObjectName("nowPlayingOverlayCover")
        cover.setFixedSize(cover_size, cover_size)
        cover.set_compact_circle(False)
        cover.clear_art("♪")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setStyleSheet("font-size: 72px; color: #6f91d9; background: #101521; border-radius: 24px;")
        layout.addWidget(cover, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel()
        title.setObjectName("nowPlayingOverlayTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        layout.addWidget(title)

        detail = QLabel()
        detail.setObjectName("nowPlayingOverlayMeta")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setStyleSheet("font-size: 15px;")
        layout.addWidget(detail)

        album = QLabel(self._t("Albüm: bekleniyor"))
        album.setObjectName("nowPlayingOverlayMeta")
        album.setAlignment(Qt.AlignmentFlag.AlignCenter)
        album.setStyleSheet("font-size: 13px;")
        layout.addWidget(album)

        progress = QProgressBar()
        progress.setObjectName("nowPlayingOverlayProgress")
        progress.setRange(0, 1000)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setMaximumWidth(760)
        layout.addWidget(progress, alignment=Qt.AlignmentFlag.AlignCenter)
        timeline = QLabel("00:00 / 00:00")
        timeline.setObjectName("nowPlayingOverlayStatus")
        timeline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timeline.setStyleSheet("font-size: 13px;")
        layout.addWidget(timeline)

        status = QLabel()
        status.setObjectName("nowPlayingOverlayStatus")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet("font-size: 14px;")
        layout.addWidget(status)
        visualizer = QLabel("▂ ▄ ▆ ▃ ▅")
        visualizer.setObjectName("nowPlayingOverlayMeta")
        visualizer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        visualizer.setStyleSheet("font-size: 18px; color: #6f91d9; letter-spacing: 4px;")
        layout.addWidget(visualizer)
        layout.addStretch(1)

        clock = QLabel()
        clock.setObjectName("nowPlayingOverlayClock")
        clock.setStyleSheet("font-size: 26px; font-weight: 700;")
        date = QLabel()
        date.setObjectName("nowPlayingOverlayDate")
        date.setStyleSheet("font-size: 15px;")
        platform = QLabel(self._t("Platform: bekleniyor"))
        platform.setObjectName("nowPlayingOverlayDate")
        platform.setStyleSheet("font-size: 15px;")
        volume_label = QLabel(self._t("Ses: okunuyor"))
        volume_label.setObjectName("nowPlayingOverlayDate")
        volume_slider = QSlider(Qt.Orientation.Horizontal)
        volume_slider.setRange(0, 100)
        volume_slider.setValue(50)
        volume_slider.setMinimumWidth(150)
        volume_slider.sliderReleased.connect(self._set_fullscreen_volume)

        def _icon_button(icon_name: str, tooltip: str, object_name: str = "nowPlayingControlButton") -> QPushButton:
            button = QPushButton()
            button.setObjectName(object_name)
            button.setIcon(netops_icon(icon_name, color="#D8DEE9", size=22))
            button.setIconSize(QSize(22, 22))
            button.setToolTip(self._t(tooltip))
            button.setAccessibleName(self._t(tooltip))
            button.setMinimumSize(48, 42)
            return button

        previous = _icon_button("previous", "Önceki")
        previous.clicked.connect(lambda: self._fullscreen_media_action("previous"))
        play_pause = _icon_button("play", "Oynat / Duraklat")
        play_pause.clicked.connect(lambda: self._fullscreen_media_action("play_pause"))
        mute = _icon_button("volume", "Sessize al")
        mute.clicked.connect(lambda: self._fullscreen_media_action("mute_toggle"))
        next_button = _icon_button("next", "Sonraki")
        next_button.clicked.connect(lambda: self._fullscreen_media_action("next"))
        close_button = _icon_button(
            "close",
            "Now Playing'i kapat  (Esc yerine)",
            "nowPlayingCloseButton",
        )
        close_button.setMinimumSize(42, 42)
        close_button.clicked.connect(self._close_now_playing_fullscreen)

        left_status = QWidget()
        left_status_layout = QHBoxLayout(left_status)
        left_status_layout.setContentsMargins(0, 0, 0, 0)
        left_status_layout.setSpacing(10)
        left_status_layout.addWidget(clock)
        left_status_layout.addWidget(date)
        left_status_layout.addWidget(platform)

        media_controls = QWidget()
        media_controls.setObjectName("nowPlayingMediaControls")
        media_controls_layout = QHBoxLayout(media_controls)
        media_controls_layout.setContentsMargins(0, 0, 0, 0)
        media_controls_layout.setSpacing(10)
        media_controls_layout.addWidget(previous)
        media_controls_layout.addWidget(play_pause)
        media_controls_layout.addWidget(mute)
        media_controls_layout.addWidget(next_button)

        right_status = QWidget()
        right_status_layout = QHBoxLayout(right_status)
        right_status_layout.setContentsMargins(0, 0, 0, 0)
        right_status_layout.setSpacing(10)
        right_status_layout.addWidget(volume_label)
        right_status_layout.addWidget(volume_slider)
        right_status_layout.addWidget(close_button)

        footer = QGridLayout()
        footer.setContentsMargins(0, 10, 0, 0)
        footer.setHorizontalSpacing(18)
        footer.setColumnStretch(0, 1)
        footer.setColumnStretch(2, 1)
        footer.addWidget(
            left_status,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        footer.addWidget(media_controls, 0, 1, Qt.AlignmentFlag.AlignCenter)
        footer.addWidget(
            right_status,
            0,
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addLayout(footer)

        self._now_playing_overlay = overlay
        self._now_playing_overlay_values = {
            "heading": heading,
            "title": title,
            "detail": detail,
            "album": album,
            "timeline": timeline,
            "status": status,
            "clock": clock,
            "date": date,
        }
        self._now_playing_overlay_cover = cover
        self._now_playing_overlay_platform = platform
        self._now_playing_overlay_album = album
        self._now_playing_overlay_timeline = timeline
        self._now_playing_overlay_progress = progress
        self._now_playing_overlay_volume_label = volume_label
        self._now_playing_overlay_volume_slider = volume_slider
        self._now_playing_overlay_play_pause = play_pause
        self._now_playing_overlay_mute = mute
        self._now_playing_overlay_visualizer = visualizer
        overlay.showFullScreen()
        self._now_playing_overlay_timer.start()
        self._now_playing_visualizer_timer.start()
        self._refresh_now_playing_fullscreen()
        self._refresh_fullscreen_volume()

    def _close_now_playing_fullscreen(self) -> None:
        overlay = self._now_playing_overlay
        self._now_playing_overlay_timer.stop()
        self._now_playing_visualizer_timer.stop()
        self._now_playing_overlay = None
        self._now_playing_overlay_values = {}
        self._now_playing_overlay_cover = None
        self._now_playing_overlay_platform = None
        self._now_playing_overlay_album = None
        self._now_playing_overlay_timeline = None
        self._now_playing_overlay_progress = None
        self._now_playing_overlay_volume_label = None
        self._now_playing_overlay_volume_slider = None
        self._now_playing_overlay_play_pause = None
        self._now_playing_overlay_mute = None
        self._now_playing_overlay_visualizer = None
        if overlay is not None:
            overlay.close()
            overlay.deleteLater()

    def _refresh_now_playing_fullscreen(self) -> None:
        overlay = self._now_playing_overlay
        if overlay is None or not overlay.isVisible():
            self._now_playing_overlay_timer.stop()
            return

        result = self.backend.run("now_playing")
        result = result if isinstance(result, dict) else {}
        title = str(result.get("title", "") or "").strip()
        has_media = bool(title) and not result.get("error") and title.lower() not in {
            "müzik bekleniyor",
            "bekleniyor",
            "unknown",
        }
        values = self._now_playing_overlay_values
        now = datetime.now()
        values["clock"].setText(now.strftime("%H:%M"))
        values["date"].setText(now.strftime("%d.%m.%Y"))

        if has_media:
            artist = str(result.get("artist", "") or "").strip()
            app = str(result.get("app", result.get("source", "")) or "").strip()
            album = str(result.get("album", "") or "").strip()
            playback = str(result.get("playback_status", "Oynatılıyor") or "Oynatılıyor")
            detail = " • ".join(item for item in (artist, app) if item) or self._t("Kaynak bilgisi yok")
            values["heading"].setText(self._t(native_now_playing_contract()["fullscreen_title"]))
            values["title"].setText(title)
            values["detail"].setText(detail)
            if self._now_playing_overlay_album is not None:
                self._now_playing_overlay_album.setText(f"{self._t('Albüm')}: {self._t(album or 'Bilinmiyor')}")
            values["status"].setText(f"{self._t('Durum')}: {self._t(playback)}")
            if self._now_playing_overlay_platform is not None:
                self._now_playing_overlay_platform.setText(f"{self._t('Platform')}: {self._t(app or 'Bilinmiyor')}")
            if self._now_playing_overlay_play_pause is not None:
                paused = playback.casefold() in {"paused", "pause", "duraklatıldı", "durduruldu", "stopped", "stop"}
                self._now_playing_overlay_play_pause.setIcon(
                    netops_icon("play" if paused else "pause", color="#D8DEE9", size=22)
                )
                self._now_playing_overlay_play_pause.setToolTip(
                    self._t("Oynat / Duraklat")
                )
            self._update_fullscreen_timeline(result)
        else:
            values["heading"].setText(self._t(native_now_playing_contract()["standby_title"]))
            values["title"].setText(self._t("Müzik bekleniyor"))
            values["detail"].setText(self._t("Şu an çalan parça olduğunda bilgiler burada görünür."))
            if self._now_playing_overlay_album is not None:
                self._now_playing_overlay_album.setText(self._t("Albüm: bekleniyor"))
            values["status"].setText(self._t("Now Playing hazır"))
            if self._now_playing_overlay_platform is not None:
                self._now_playing_overlay_platform.setText(self._t("Platform: bekleniyor"))
            if self._now_playing_overlay_play_pause is not None:
                self._now_playing_overlay_play_pause.setIcon(
                    netops_icon("play", color="#D8DEE9", size=22)
                )
            self._update_fullscreen_timeline({})

        cover_path = str(result.get("cover_path", "") or "")
        cover = self._now_playing_overlay_cover
        if cover is not None and cover_path and Path(cover_path).exists():
            pixmap = load_cover_pixmap(cover_path)
            if not pixmap.isNull():
                if isinstance(cover, NowPlayingCover):
                    cover.set_art(pixmap, animate=False)
                else:
                    cover.setPixmap(
                        pixmap.scaled(
                            300,
                            300,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    cover.setText("")
        elif cover is not None:
            if isinstance(cover, NowPlayingCover):
                cover.clear_art("♪")
            else:
                cover.setPixmap(QPixmap())
                cover.setText("♪")

    def _update_fullscreen_timeline(self, result: dict[str, Any]) -> None:
        progress = self._now_playing_overlay_progress
        timeline = self._now_playing_overlay_timeline
        if progress is None or timeline is None:
            return
        try:
            position = max(0.0, float(result.get("position_seconds", 0) or 0))
            duration = max(0.0, float(result.get("duration_seconds", 0) or 0))
        except (TypeError, ValueError):
            position, duration = 0.0, 0.0
        if duration <= 0:
            progress.setValue(0)
            timeline.setText(self._t("Süre bilgisi bekleniyor"))
            return
        progress.setValue(max(0, min(1000, int((position / duration) * 1000))))
        position_i = int(position)
        duration_i = int(duration)
        timeline.setText(
            f"{position_i // 60:02d}:{position_i % 60:02d} / "
            f"{duration_i // 60:02d}:{duration_i % 60:02d}"
        )

    def _refresh_fullscreen_visualizer(self) -> None:
        visualizer = self._now_playing_overlay_visualizer
        if visualizer is None or self._now_playing_overlay is None or not self._now_playing_overlay.isVisible():
            self._now_playing_visualizer_timer.stop()
            return
        if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
            visualizer.setText("—")
            return
        title = self._now_playing_overlay_values.get("title")
        title_text = title.text() if title is not None else "netops"
        seed = sum(ord(char) for char in title_text) % 17
        levels = "▁▂▃▄▅▆▇█"
        phase = self._now_playing_visualizer_phase * 0.34
        bars = []
        for index in range(10):
            wave = (math.sin(phase + index * 0.72 + seed) + 1) / 2
            wave2 = (math.sin(phase * 1.7 + index * 1.18) + 1) / 2
            level = int(max(0, min(len(levels) - 1, 1 + (wave * 3.2) + (wave2 * 2.4))))
            bars.append(levels[level])
        visualizer.setText(" ".join(bars))
        self._now_playing_visualizer_phase += 1

    def _set_fullscreen_volume(self) -> None:
        slider = self._now_playing_overlay_volume_slider
        label = self._now_playing_overlay_volume_label
        if slider is None:
            return
        value = slider.value()
        result = self.backend.run("media_control", f"volume_set:{value}")
        if label is not None:
            label.setText(
                f"{self._t('Ses')}: %{value}"
                if not (isinstance(result, dict) and result.get("ok") is False)
                else self._t("Ses: ayarlanamadı")
            )

    def _refresh_fullscreen_volume(self) -> None:
        slider = self._now_playing_overlay_volume_slider
        label = self._now_playing_overlay_volume_label
        if slider is None:
            return
        result = self.backend.run("media_control", "volume_get")
        if not isinstance(result, dict) or result.get("value") is None:
            if label is not None:
                label.setText(self._t("Ses: okunamadı"))
            return
        try:
            value = max(0, min(100, int(float(result["value"]))))
        except (TypeError, ValueError):
            return
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)
        if label is not None:
            label.setText(f"{self._t('Ses')}: %{value}")
        if self._now_playing_overlay_mute is not None:
            muted = result.get("muted") is True
            self._now_playing_overlay_mute.setIcon(
                netops_icon("volume-x" if muted else "volume", color="#D8DEE9", size=22)
            )
            self._now_playing_overlay_mute.setToolTip(self._t("Sesi aç" if muted else "Sessize al"))

    def _fullscreen_media_action(self, action: str) -> None:
        result = self.backend.run("media_control", action)
        if action == "mute_toggle" and self._now_playing_overlay_mute is not None and isinstance(result, dict):
            muted = result.get("muted") is True
            self._now_playing_overlay_mute.setIcon(
                netops_icon("volume-x" if muted else "volume", color="#D8DEE9", size=22)
            )
            self._now_playing_overlay_mute.setToolTip(self._t("Sesi aç" if muted else "Sessize al"))
        QTimer.singleShot(250, self._refresh_now_playing_fullscreen)

    def _media_action(self, action: str) -> None:
        self.backend.run("media_control", action)
        QTimer.singleShot(250, self._refresh_now_playing)

    def _refresh_automations(self) -> None:
        result = self.backend.run("automations")
        rows = result if isinstance(result, list) else []
        self._automations_table.setRowCount(len(rows))
        for row, automation in enumerate(rows):
            automation = automation if isinstance(automation, dict) else {}
            values = (
                automation.get("name", self._t("Bilinmiyor")),
                self._t("Evet" if automation.get("enabled") else "Hayır"),
                automation.get("trigger_type", self._t("Bilinmiyor")),
            )
            for column, value in enumerate(values):
                self._automations_table.setItem(row, column, QTableWidgetItem(str(value)))


def run_native_qt_app(backend: QtBackend | None = None) -> int:
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(backend=backend)
    if native_window_contract()["start_maximized"]:
        window.showMaximized()
    else:
        window.show()
    if os.environ.get("NETOPS_REDUCE_MOTION") == "1":
        window.setWindowOpacity(1.0)
    else:
        animation = QPropertyAnimation(window, b"windowOpacity", window)
        animation.setDuration(int(native_motion_contract()["startup_ms"]))
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        window._startup_animation = animation
    return app.exec()


__all__ = [
    "NetOpsQtWindow",
    "native_animation_contract",
    "native_brand_contract",
    "native_command_bar_contract",
    "native_help_center_contract",
    "native_legacy_layout_contract",
    "native_motion_contract",
    "native_now_playing_contract",
    "native_page_keys",
    "native_sidebar_contract",
    "native_sidebar_chat_contract",
    "native_sidebar_extension_contract",
    "native_sidebar_icon_contract",
    "native_sidebar_motion_contract",
    "native_settings_animation_contract",
    "native_visual_contract",
    "native_window_contract",
    "run_native_qt_app",
]
