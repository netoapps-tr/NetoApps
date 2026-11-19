"""Optional live YouTube Music surface for the NetOps Now Playing view.

The Qt WebEngine process is deliberately isolated from the CustomTkinter UI
process.  A slow page, a renderer crash, or a missing WebEngine installation
must not take down NetOps itself.
"""
from __future__ import annotations

import multiprocessing
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from typing import Any


YOUTUBE_MUSIC_URL = "https://music.youtube.com/"


def _panel_log(message: str) -> None:
    try:
        log_dir = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            "NetoAssistant",
            "logs",
        )
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "youtube_music_panel.log"), "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def webengine_available() -> bool:
    """Return whether the safe native Chrome docking path is available."""
    return _native_window_api() is not None


def _set_native_parent(child_hwnd: int, parent_hwnd: int, width: int, height: int) -> None:
    """Dock a Qt top-level window into a Tk host frame on Windows."""
    if os.name != "nt" or not child_hwnd or not parent_hwnd:
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        long_ptr = ctypes.sizeof(ctypes.c_void_p)
        get_long = user32.GetWindowLongPtrW if long_ptr == 8 else user32.GetWindowLongW
        set_long = user32.SetWindowLongPtrW if long_ptr == 8 else user32.SetWindowLongW
        get_long.restype = ctypes.c_ssize_t
        set_long.restype = ctypes.c_ssize_t
        style = int(get_long(int(child_hwnd), -16))
        style = (style | 0x40000000 | 0x10000000) & ~0x80000000  # WS_CHILD + WS_VISIBLE, no popup.
        set_long(int(child_hwnd), -16, style)
        user32.SetParent(int(child_hwnd), int(parent_hwnd))
        user32.MoveWindow(int(child_hwnd), 0, 0, max(1, int(width)), max(1, int(height)), True)
        user32.ShowWindow(int(child_hwnd), 5)
    except Exception:
        pass


def _native_window_api():
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        return ctypes, wintypes, user32
    except Exception:
        return None


def _find_youtube_music_window() -> int:
    """Find the standalone Chrome YouTube Music window, if it is open."""
    api = _native_window_api()
    if api is None:
        return 0
    ctypes, wintypes, user32 = api
    try:
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found = {"hwnd": 0}

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            title = title_buffer.value.strip().lower()
            if title not in {"youtube music", "youtube music - google chrome"}:
                return True
            found["hwnd"] = int(hwnd)
            return False

        user32.EnumWindows(enum_proc(callback), 0)
        return int(found["hwnd"])
    except Exception:
        return 0


def _native_window_snapshot(hwnd: int) -> dict[str, int]:
    api = _native_window_api()
    if api is None:
        return {}
    ctypes, _wintypes, user32 = api
    try:
        class Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = Rect()
        user32.GetWindowRect(int(hwnd), ctypes.byref(rect))
        long_ptr = ctypes.sizeof(ctypes.c_void_p)
        get_long = user32.GetWindowLongPtrW if long_ptr == 8 else user32.GetWindowLongW
        return {
            "parent": int(user32.GetParent(int(hwnd)) or 0),
            "style": int(get_long(int(hwnd), -16)),
            "exstyle": int(get_long(int(hwnd), -20)),
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        return {}


def _restore_native_window(hwnd: int, snapshot: dict[str, int]) -> None:
    api = _native_window_api()
    if api is None or not hwnd or not snapshot:
        return
    ctypes, _wintypes, user32 = api
    try:
        long_ptr = ctypes.sizeof(ctypes.c_void_p)
        set_long = user32.SetWindowLongPtrW if long_ptr == 8 else user32.SetWindowLongW
        user32.SetParent(int(hwnd), int(snapshot.get("parent", 0)))
        set_long(int(hwnd), -16, int(snapshot.get("style", 0)))
        set_long(int(hwnd), -20, int(snapshot.get("exstyle", 0)))
        user32.SetWindowPos(
            int(hwnd), 0,
            int(snapshot.get("left", 0)), int(snapshot.get("top", 0)),
            max(1, int(snapshot.get("right", 1)) - int(snapshot.get("left", 0))),
            max(1, int(snapshot.get("bottom", 1)) - int(snapshot.get("top", 0))),
            0x0040 | 0x0010,
        )
        user32.ShowWindow(int(hwnd), 5)
    except Exception:
        pass


def _webengine_worker(command_queue, parent_hwnd: int, width: int, height: int, initial_url: str) -> None:
    """Run a single WebEngine view in a child process."""
    try:
        from PyQt6.QtCore import QTimer, Qt, QUrl
        from PyQt6.QtGui import QColor
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication, QMainWindow

        app = QApplication([])
        profile_dir = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            "NetoAssistant",
            "youtube_music_webengine",
        )
        os.makedirs(profile_dir, exist_ok=True)
        profile = QWebEngineProfile("netops-youtube-music", app)
        profile.setPersistentStoragePath(profile_dir)
        profile.setCachePath(os.path.join(profile_dir, "cache"))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)

        page = profile.newPage()
        view = QWebEngineView()
        view.setPage(page)
        view.setStyleSheet("background:#0d1016; border:0;")

        window = QMainWindow()
        window.setWindowTitle("YouTube Music")
        window.setCentralWidget(view)
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        window.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        window.setAutoFillBackground(True)
        palette = window.palette()
        palette.setColor(window.backgroundRole(), QColor("#0d1016"))
        window.setPalette(palette)
        window.resize(max(1, int(width)), max(1, int(height)))
        window.show()
        app.processEvents()
        _set_native_parent(int(window.winId()), int(parent_hwnd), width, height)
        view.setUrl(QUrl(str(initial_url or YOUTUBE_MUSIC_URL)))

        def poll_commands() -> None:
            for _ in range(12):
                try:
                    command = command_queue.get_nowait()
                except queue.Empty:
                    return
                except Exception:
                    return
                if not isinstance(command, dict):
                    continue
                action = str(command.get("action") or "").lower().strip()
                if action == "resize":
                    new_width = max(1, int(command.get("width") or width))
                    new_height = max(1, int(command.get("height") or height))
                    window.resize(new_width, new_height)
                    _set_native_parent(int(window.winId()), int(parent_hwnd), new_width, new_height)
                elif action == "open_url":
                    url = str(command.get("url") or YOUTUBE_MUSIC_URL).strip()
                    if url.startswith(("https://music.youtube.com/", "https://www.youtube.com/")):
                        view.setUrl(QUrl(url))
                elif action == "reload":
                    view.reload()
                elif action == "close":
                    window.close()
                    app.quit()
                    return

        timer = QTimer(window)
        timer.timeout.connect(poll_commands)
        timer.start(120)
        app.exec()
    except Exception as exc:
        _panel_log("worker failed: " + repr(exc) + "\n" + traceback.format_exc())
        # The parent detects the stopped process and keeps the rest of NetOps alive.
        return


class _SocketCommandQueue:
    """Small non-blocking queue adapter used by the standalone Qt worker."""

    def __init__(self, connection: socket.socket) -> None:
        self.connection = connection
        self.buffer = b""

    def get_nowait(self) -> dict[str, Any]:
        try:
            self.buffer += self.connection.recv(65536)
        except (BlockingIOError, TimeoutError):
            raise queue.Empty
        except Exception:
            raise queue.Empty
        if not self.buffer:
            raise queue.Empty
        if b"\n" not in self.buffer:
            raise queue.Empty
        raw, self.buffer = self.buffer.split(b"\n", 1)
        try:
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}


def _run_standalone_worker(argv: list[str]) -> int:
    """Entry point for the standalone Qt WebEngine subprocess."""
    try:
        values = dict(zip(argv[::2], argv[1::2]))
        port = int(values["--port"])
        token = str(values["--token"])
        parent_hwnd = int(values["--parent-hwnd"])
        width = int(values["--width"])
        height = int(values["--height"])
        initial_url = str(values.get("--url") or YOUTUBE_MUSIC_URL)
        connection = socket.create_connection(("127.0.0.1", port), timeout=8.0)
        connection.sendall((json.dumps({"action": "hello", "token": token}) + "\n").encode("utf-8"))
        connection.setblocking(False)
        _webengine_worker(_SocketCommandQueue(connection), parent_hwnd, width, height, initial_url)
        try:
            connection.close()
        except Exception:
            pass
        return 0
    except Exception as exc:
        _panel_log("standalone worker failed: " + repr(exc) + "\n" + traceback.format_exc())
        return 1


class YouTubeMusicPanel:
    """Temporarily dock the standalone YouTube Music Chrome window into Tk."""

    def __init__(self) -> None:
        self._hwnd = 0
        self._snapshot: dict[str, int] = {}
        self._parent_hwnd = 0
        self._lock = threading.RLock()

    def is_alive(self) -> bool:
        with self._lock:
            api = _native_window_api()
            if api is None or not self._hwnd:
                return False
            return bool(api[2].IsWindow(int(self._hwnd)))

    def open(self, parent_hwnd: int, width: int, height: int, url: str = YOUTUBE_MUSIC_URL) -> bool:
        if not parent_hwnd:
            return False
        with self._lock:
            if self.is_alive():
                self.resize(width, height)
                return True
            if not webengine_available():
                return False
            self.close()
            hwnd = _find_youtube_music_window()
            if not hwnd:
                try:
                    import webbrowser
                    webbrowser.open(YOUTUBE_MUSIC_URL, new=1, autoraise=True)
                except Exception:
                    pass
                # Do not block the NetOps UI while Chrome creates its app window.
                return False
            self._hwnd = int(hwnd)
            self._parent_hwnd = int(parent_hwnd)
            self._snapshot = _native_window_snapshot(self._hwnd)
            if not self._snapshot:
                self._hwnd = 0
                return False
            _set_native_parent(self._hwnd, self._parent_hwnd, width, height)
            return True

    def _send(self, action: str, **payload: Any) -> bool:
        # Native Chrome receives user input directly; only resize needs a native call.
        return bool(action == "resize" and self.is_alive())

    def resize(self, width: int, height: int) -> bool:
        if not self.is_alive():
            return False
        try:
            _set_native_parent(self._hwnd, self._parent_hwnd, max(1, int(width)), max(1, int(height)))
            return True
        except Exception:
            return False

    def open_url(self, url: str) -> bool:
        url = str(url or "").strip()
        if not url.startswith(("https://music.youtube.com/", "https://www.youtube.com/")):
            return False
        if not self.is_alive():
            return False
        try:
            import webbrowser
            return bool(webbrowser.open(url, new=1, autoraise=True))
        except Exception:
            return False

    def reload(self) -> bool:
        return self.open_url(YOUTUBE_MUSIC_URL)

    def close(self) -> None:
        with self._lock:
            if self._hwnd and self._snapshot:
                _restore_native_window(self._hwnd, self._snapshot)
            self._hwnd = 0
            self._parent_hwnd = 0
            self._snapshot = {}


_PANEL: YouTubeMusicPanel | None = None


def get_panel() -> YouTubeMusicPanel:
    global _PANEL
    if _PANEL is None:
        _PANEL = YouTubeMusicPanel()
    return _PANEL


def close_panel() -> None:
    global _PANEL
    if _PANEL is not None:
        _PANEL.close()


if __name__ == "__main__" and "--netops-youtube-worker" in sys.argv:
    raise SystemExit(_run_standalone_worker(sys.argv[sys.argv.index("--netops-youtube-worker") + 1 :]))

