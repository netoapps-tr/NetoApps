"""NetOps update user interface.

Imports are lightweight; CustomTkinter is loaded only when a window/panel is
actually created.
"""
from __future__ import annotations

import os
import threading
import time
import webbrowser
from typing import Any, Callable, Dict, Optional

import neto_updater

_STARTUP_RUNNING = False
_ACTIVE_PROGRESS: Any = None
_LAST_DIALOG_RELEASE_ID: Any = None


def _dispatch(root: Any, callback: Callable[[], Any], delay: int = 0) -> None:
    try:
        if root is not None and root.winfo_exists():
            root.after(max(0, int(delay)), callback)
            return
    except Exception:
        pass
    try:
        callback()
    except Exception:
        pass


def _notify(callback: Optional[Callable[[str], Any]], message: str) -> None:
    if callable(callback):
        try:
            callback(str(message))
        except Exception:
            pass


def _language() -> str:
    try:
        from lang import get_lang
        return "tr" if str(get_lang()).lower().startswith("tr") else "en"
    except Exception:
        return "tr"


def _t(tr: str, en: str) -> str:
    return tr if _language() == "tr" else en


def _result_text(result: Dict[str, Any]) -> str:
    if result.get("available"):
        if not result.get("verified", result.get("asset_digest")):
            return _t(
                f"Yeni sürüm bulundu ama SHA-256 doğrulaması yok: {result.get('tag_name') or result.get('latest_version') or '—'}",
                f"New version found but SHA-256 verification is missing: {result.get('tag_name') or result.get('latest_version') or '—'}",
            )
        return _t(
            f"Yeni sürüm hazır: {result.get('tag_name') or result.get('latest_version') or '—'}",
            f"New version available: {result.get('tag_name') or result.get('latest_version') or '—'}",
        )
    if result.get("error"):
        return _t(
            f"Kontrol tamamlanamadı: {result.get('error')}",
            f"Update check failed: {result.get('error')}",
        )
    return _t(
        f"Güncelsin. Kurulu sürüm: {result.get('current_version') or neto_updater.get_current_version()}",
        f"Up to date. Installed version: {result.get('current_version') or neto_updater.get_current_version()}",
    )


def _handle_result(
    root: Any,
    result: Dict[str, Any],
    notify_callback: Optional[Callable[[str], Any]],
    manual: bool,
    callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> None:
    if result.get("available") and not manual:
        show_update_dialog(root, result, notify_callback=notify_callback)
    elif manual:
        _notify(notify_callback, _result_text(result))
    if callable(callback):
        try:
            callback(result)
        except Exception:
            pass


def schedule_startup_check(
    root: Any,
    notify_callback: Optional[Callable[[str], Any]] = None,
    delay_ms: int = 650,
    include_prerelease: bool = False,
    **_: Any,
) -> Any:
    def start() -> None:
        global _STARTUP_RUNNING
        if _STARTUP_RUNNING:
            return
        _STARTUP_RUNNING = True

        def worker() -> None:
            global _STARTUP_RUNNING
            try:
                result = neto_updater.check_for_updates(force=True, include_prerelease=include_prerelease)
                _dispatch(root, lambda: _handle_result(root, result, notify_callback, False))
            finally:
                _STARTUP_RUNNING = False

        threading.Thread(target=worker, name="NetoStartupUpdateCheck", daemon=True).start()

    try:
        return root.after(max(0, int(delay_ms)), start)
    except Exception:
        start()
        return None


def manual_check(
    root: Any = None,
    notify_callback: Optional[Callable[[str], Any]] = None,
    include_prerelease: bool = False,
    callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    **_: Any,
) -> threading.Thread:
    _notify(notify_callback, _t("Güncellemeler kontrol ediliyor...", "Checking for updates..."))

    def worker() -> None:
        result = neto_updater.check_for_updates(force=True, include_prerelease=include_prerelease)
        _dispatch(root, lambda: _handle_result(root, result, notify_callback, True, callback))

    thread = threading.Thread(target=worker, name="NetoManualUpdateCheck", daemon=True)
    thread.start()
    return thread


def check_now(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


def check_updates(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


def check_for_updates_ui(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


def open_update_window(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


def show_update_window(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


def create_update_window(*args: Any, **kwargs: Any) -> threading.Thread:
    return manual_check(*args, **kwargs)


class _ProgressWindow:
    def __init__(self, root: Any, update: Dict[str, Any], notify_callback=None) -> None:
        import customtkinter as ctk

        self.root = root
        self.update = update
        self.notify_callback = notify_callback
        self.cancelled = False
        self.window = ctk.CTkToplevel(root)
        self.window.title(_t("Neto Güncellemesi", "Neto Update"))
        self.window.geometry("500x260")
        self.window.resizable(False, False)
        self.window.transient(root)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        self.title = ctk.CTkLabel(
            self.window,
            text=_t("Güncelleme indiriliyor", "Downloading update"),
            font=("Segoe UI Semibold", 21),
        )
        self.title.pack(pady=(28, 8))
        self.status = ctk.CTkLabel(self.window, text="0%", font=("Segoe UI", 12))
        self.status.pack(pady=(0, 10))
        self.progress = ctk.CTkProgressBar(self.window, width=390)
        self.progress.set(0)
        self.progress.pack(pady=8)
        self.cancel_button = ctk.CTkButton(
            self.window,
            text=_t("İptal", "Cancel"),
            width=120,
            command=self._cancel,
        )
        self.cancel_button.pack(pady=(18, 0))
        threading.Thread(target=self._worker, name="NetoUpdateDownload", daemon=True).start()

    def _cancel(self) -> None:
        self.cancelled = True
        try:
            self.window.destroy()
        except Exception:
            pass

    def _progress(self, done: int, total: int) -> None:
        if self.cancelled:
            raise RuntimeError(_t("İndirme iptal edildi.", "Download cancelled."))
        fraction = done / total if total else 0.0

        def apply() -> None:
            try:
                self.progress.set(max(0.0, min(1.0, fraction)))
                self.status.configure(text=f"{fraction * 100:.1f}%" if total else f"{done / 1024 / 1024:.1f} MB")
            except Exception:
                pass

        _dispatch(self.root, apply)

    def _worker(self) -> None:
        try:
            path = neto_updater.download_update(self.update, progress_callback=self._progress)
            if self.cancelled:
                return
            result = neto_updater.install_update(
                path,
                restart=True,
                release_id=self.update.get("release_id"),
                tag=str(self.update.get("tag_name") or ""),
            )
            if not result.get("ok"):
                raise RuntimeError(_t("İndirilen paket otomatik kurulamıyor.", "Downloaded package cannot be installed automatically."))
            _notify(self.notify_callback, _t("Güncelleme indirildi; Neto yeniden başlatılıyor.", "Update downloaded; Neto is restarting."))

            def close_app() -> None:
                try:
                    self.window.destroy()
                except Exception:
                    pass
                try:
                    self.root.quit()
                    self.root.destroy()
                except Exception:
                    pass
                threading.Thread(target=lambda: (time.sleep(1.2), os._exit(0)), daemon=True).start()

            _dispatch(self.root, close_app, 600)
        except Exception as exc:
            message = _t(f"Güncelleme kurulamadı: {exc}", f"Update could not be installed: {exc}")
            _notify(self.notify_callback, message)

            def show_error() -> None:
                try:
                    self.title.configure(text=_t("Güncelleme başarısız", "Update failed"))
                    self.status.configure(text=message, wraplength=420)
                    self.progress.set(0)
                    self.cancel_button.configure(text=_t("Kapat", "Close"))
                except Exception:
                    pass

            _dispatch(self.root, show_error)


def start_download_and_install(root: Any, update: Dict[str, Any], notify_callback=None) -> Any:
    global _ACTIVE_PROGRESS
    try:
        if _ACTIVE_PROGRESS is not None and _ACTIVE_PROGRESS.window.winfo_exists():
            _ACTIVE_PROGRESS.window.lift()
            return _ACTIVE_PROGRESS
    except Exception:
        _ACTIVE_PROGRESS = None
    if not update or not update.get("available"):
        return None
    if not update.get("verified", update.get("asset_digest")):
        _notify(
            notify_callback,
            _t(
                "Bu sürüm SHA-256 ile doğrulanamadığı için kurulum kapalı.",
                "This release could not be verified with SHA-256, so install is disabled.",
            ),
        )
        return None
    if not update.get("download_url") and update.get("update_mode") != "system_files":
        try:
            webbrowser.open(str(update.get("html_url") or neto_updater.RELEASES_URL))
        except Exception:
            pass
        return None
    _ACTIVE_PROGRESS = _ProgressWindow(root, update, notify_callback)
    return _ACTIVE_PROGRESS


def download_and_install(
    update=None,
    root=None,
    notify_callback=None,
    include_prerelease: bool = False,
    **_: Any,
) -> Any:
    update = update or neto_updater.check_for_updates(
        force=True,
        include_prerelease=bool(include_prerelease),
    )
    return start_download_and_install(root, update, notify_callback=notify_callback)


def show_update_dialog(root: Any, update: Dict[str, Any], notify_callback=None) -> None:
    global _LAST_DIALOG_RELEASE_ID
    if not update.get("available"):
        return
    release_id = update.get("release_id") or update.get("tag_name")
    if release_id and str(release_id) == str(_LAST_DIALOG_RELEASE_ID):
        return
    _LAST_DIALOG_RELEASE_ID = release_id
    try:
        neto_updater.mark_release_notified(update)
    except Exception:
        pass
    _notify(notify_callback, _result_text(update))
    try:
        import customtkinter as ctk

        window = ctk.CTkToplevel(root)
        window.title(_t("NetOps Güncellemesi", "NetOps Update"))
        window.geometry("500x320")
        window.resizable(False, False)
        window.transient(root)
        window.grab_set()
        ctk.CTkLabel(window, text="↑", font=("Segoe UI Black", 44)).pack(pady=(25, 3))
        ctk.CTkLabel(
            window,
            text=_t("Yeni Neto sürümü hazır", "A new Neto version is ready"),
            font=("Segoe UI Semibold", 22),
        ).pack()
        ctk.CTkLabel(
            window,
            text=f"{neto_updater.get_current_version()}  →  {update.get('tag_name') or update.get('latest_version') or '—'}",
            font=("Segoe UI", 13),
        ).pack(pady=(8, 20))
        installable = bool(update.get("verified", update.get("asset_digest")))
        if not installable:
            ctk.CTkLabel(
                window,
                text=_t(
                    "Bu sürüm SHA-256 ile doğrulanamadı. Kurulum kapalı.",
                    "This release could not be verified with SHA-256. Install is disabled.",
                ),
                font=("Segoe UI", 12),
                wraplength=430,
                justify="center",
            ).pack(pady=(0, 8))
        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.pack(fill="x", padx=35, pady=(12, 20))
        ctk.CTkButton(actions, text=_t("Daha Sonra", "Later"), width=150, command=window.destroy).pack(side="left")
        ctk.CTkButton(
            actions,
            text=_t("Güncelle ve Kur", "Update and Install"),
            width=210,
            state="normal" if installable else "disabled",
            command=lambda: (window.destroy(), start_download_and_install(root, update, notify_callback)),
        ).pack(side="right")
    except Exception:
        pass


def create_update_panel(parent: Any, notify_callback=None, **_: Any) -> Any:
    import customtkinter as ctk

    root = parent.winfo_toplevel()
    frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
    frame.pack(fill="both", expand=True, padx=16, pady=16)
    title = ctk.CTkLabel(
        frame,
        text=_t("NetOps Güncellemeleri", "NetOps Updates"),
        font=("Segoe UI Semibold", 20),
        anchor="w",
    )
    title.pack(fill="x", pady=(0, 8))
    status = ctk.CTkLabel(frame, text=_t("Hazır", "Ready"), anchor="w", justify="left", wraplength=480)
    status.pack(fill="x", pady=(0, 12))
    button = ctk.CTkButton(frame, text=_t("Şimdi Kontrol Et", "Check Now"), width=180)
    button.pack(anchor="w")
    state: Dict[str, Any] = {"result": None}

    def done(result: Dict[str, Any]) -> None:
        state["result"] = result
        status.configure(text=_result_text(result))
        button.configure(state="normal", text=_t("Tekrar Kontrol Et", "Check Again"))
        if result.get("available") and result.get("verified", result.get("asset_digest")):
            install_button.configure(state="normal")
        else:
            install_button.configure(state="disabled")

    def check() -> None:
        button.configure(state="disabled", text=_t("Kontrol ediliyor...", "Checking..."))
        manual_check(root=root, notify_callback=notify_callback, callback=done)

    def install() -> None:
        result = state.get("result")
        if isinstance(result, dict):
            start_download_and_install(root, result, notify_callback)

    button.configure(command=check)
    install_button = ctk.CTkButton(
        frame,
        text=_t("Güncelle ve Kur", "Update and Install"),
        width=180,
        state="disabled",
        command=install,
    )
    install_button.pack(anchor="w", pady=(8, 0))
    frame.after(150, check)
    return frame
