from __future__ import annotations

import ast
import json
import py_compile
import re
import shutil
import sys
import time
from pathlib import Path

VERSION = "25.1"
MAIN_NAMES = ("asistan beta.py", "asistan_beta.py")
SETTINGS_NAME = "neto_settings_page.py"
HELPER_BEGIN = "# NETO_THREAD_GUI_FIX_V25_BEGIN"
HELPER_END = "# NETO_THREAD_GUI_FIX_V25_END"
SETTINGS_BEGIN = "# NETO_SETTINGS_WIDGET_FIX_V25_BEGIN"
SETTINGS_END = "# NETO_SETTINGS_WIDGET_FIX_V25_END"


def log(text: str) -> None:
    print(text, flush=True)


def find_project(explicit: str | None = None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path.cwd())
    desktop = Path.home() / "Desktop"
    candidates.extend([
        desktop / "NETO ASİSTAN SİLME",
        desktop / "NETO ASISTAN SILME",
    ])

    for candidate in candidates:
        try:
            candidate = candidate.expanduser().resolve()
        except Exception:
            continue
        if any((candidate / name).is_file() for name in MAIN_NAMES):
            return candidate

    raise FileNotFoundError(
        "NetOps proje klasörü bulunamadı. Bu dosyaları 'asistan beta.py' bulunan klasöre çıkarıp KUR_V25.bat çalıştır."
    )


def find_main(project: Path) -> Path:
    for name in MAIN_NAMES:
        path = project / name
        if path.is_file():
            return path
    raise FileNotFoundError("asistan beta.py bulunamadı")


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def parse(text: str, filename: str) -> ast.Module:
    return ast.parse(text, filename=filename)


def indent_block(text: str, amount: int) -> str:
    prefix = " " * amount
    return "\n".join(prefix + line if line else "" for line in text.strip("\n").splitlines())


def find_functions(text: str, filename: str, name: str, max_col: int = 8):
    tree = parse(text, filename)
    nodes = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
        and node.col_offset <= max_col
    ]
    return sorted(nodes, key=lambda n: (n.lineno, n.col_offset))


def replace_last_function(text: str, filename: str, name: str, replacement: str, required: bool = True) -> str:
    nodes = find_functions(text, filename, name)
    if not nodes:
        if required:
            raise RuntimeError(f"Fonksiyon bulunamadı: {name}")
        return text
    node = nodes[-1]
    lines = text.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [indent_block(replacement, node.col_offset) + "\n"]
    return "".join(lines)


def wrap_last_function(text: str, filename: str, name: str, wrapper: str, required: bool = True) -> str:
    original_name = f"_neto_v25_original_{name}"
    tree = parse(text, filename)
    if any(isinstance(n, ast.FunctionDef) and n.name == original_name for n in ast.walk(tree)):
        return text

    nodes = find_functions(text, filename, name)
    if not nodes:
        if required:
            raise RuntimeError(f"Fonksiyon bulunamadı: {name}")
        return text

    node = nodes[-1]
    lines = text.splitlines(keepends=True)
    segment = "".join(lines[node.lineno - 1:node.end_lineno])
    renamed, count = re.subn(
        rf"(\bdef\s+){re.escape(name)}(\s*\()",
        rf"\1{original_name}\2",
        segment,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Fonksiyon sarılamadı: {name}")

    wrapper = wrapper.replace("__ORIGINAL_NAME__", original_name)
    replacement = renamed.rstrip() + "\n\n" + indent_block(wrapper, node.col_offset) + "\n"
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    return "".join(lines)


MAIN_HELPERS = r'''
# NETO_THREAD_GUI_FIX_V25_BEGIN
_NETO_V25_CLOSING = False
_NETO_V25_ORIGINAL_CLOSE = None


def _neto_v25_widget_alive(widget) -> bool:
    if widget is None:
        return False
    try:
        return bool(int(widget.winfo_exists()))
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        return False
    except Exception:
        return False


def _neto_v25_root_alive() -> bool:
    return _neto_v25_widget_alive(globals().get("root"))


def _neto_v25_safe_after(delay_ms: int, callback, *args, owner=None):
    if threading.current_thread() is not threading.main_thread():
        return None

    root_obj = globals().get("root")
    if not _neto_v25_widget_alive(root_obj):
        return None
    if owner is not None and not _neto_v25_widget_alive(owner):
        return None

    def runner():
        if not _neto_v25_widget_alive(root_obj):
            return
        if owner is not None and not _neto_v25_widget_alive(owner):
            return
        try:
            callback(*args)
        except (tk.TclError, RuntimeError, AttributeError):
            return
        except Exception as exc:
            try:
                print(f"[V25_SAFE_AFTER_ERROR] {exc}", flush=True)
            except Exception:
                pass

    try:
        return root_obj.after(max(0, int(delay_ms)), runner)
    except (tk.TclError, RuntimeError, AttributeError):
        return None
    except Exception:
        return None


def _neto_v25_cancel_after(job) -> None:
    if not job:
        return
    root_obj = globals().get("root")
    if not _neto_v25_widget_alive(root_obj):
        return
    try:
        root_obj.after_cancel(job)
    except (tk.TclError, RuntimeError, AttributeError):
        pass
    except Exception:
        pass


def _neto_v25_safe_close():
    global _NETO_V25_CLOSING

    if _NETO_V25_CLOSING:
        return
    _NETO_V25_CLOSING = True
    globals()["now_playing_app_closing"] = True

    stop_event = globals().get("now_playing_monitor_stop")
    try:
        if stop_event is not None:
            stop_event.set()
    except Exception:
        pass

    pump_job = globals().get("now_playing_ui_pump_job")
    globals()["now_playing_ui_pump_job"] = None
    _neto_v25_cancel_after(pump_job)

    monitor_thread = globals().get("now_playing_monitor_thread")
    try:
        if monitor_thread is not None and monitor_thread.is_alive() and monitor_thread is not threading.current_thread():
            monitor_thread.join(timeout=5.0)
    except Exception:
        pass

    callback = globals().get("_NETO_V25_ORIGINAL_CLOSE")
    if callable(callback) and callback is not _neto_v25_safe_close:
        try:
            return callback()
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        except Exception as exc:
            try:
                print(f"[V25_CLOSE_CALLBACK_ERROR] {exc}", flush=True)
            except Exception:
                pass

    root_obj = globals().get("root")
    if _neto_v25_widget_alive(root_obj):
        try:
            root_obj.quit()
        except Exception:
            pass
        try:
            root_obj.destroy()
        except Exception:
            pass


globals().setdefault("now_playing_monitor_queue", queue.Queue(maxsize=1))
globals().setdefault("now_playing_monitor_stop", threading.Event())
globals().setdefault("now_playing_monitor_thread", None)
globals().setdefault("now_playing_ui_pump_job", None)
globals().setdefault("now_playing_monitor_started", False)
globals().setdefault("now_playing_monitor_last_info", None)
globals().setdefault("now_playing_monitor_last_seen", 0.0)
globals().setdefault("now_playing_app_closing", False)
# NETO_THREAD_GUI_FIX_V25_END
'''

NOW_QUEUE = r'''
def _now_playing_queue_latest(kind, payload=None):
    if globals().get("now_playing_app_closing", False):
        return

    stop_event = globals().get("now_playing_monitor_stop")
    if stop_event is not None and stop_event.is_set():
        return

    q = globals().get("now_playing_monitor_queue")
    if q is None:
        q = queue.Queue(maxsize=1)
        globals()["now_playing_monitor_queue"] = q

    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass
    except Exception:
        pass

    try:
        q.put_nowait((kind, payload, time.monotonic()))
    except queue.Full:
        pass
    except Exception:
        pass
'''

NOW_LOOP = r'''
def now_playing_monitor_loop():
    misses = 0
    last_error_print = 0.0
    stop_event = globals().get("now_playing_monitor_stop")

    if stop_event is None:
        stop_event = threading.Event()
        globals()["now_playing_monitor_stop"] = stop_event

    while not stop_event.is_set():
        try:
            info = neto_now_playing.get_current_media(force_fresh=True)
            valid = (
                isinstance(info, dict)
                and not info.get("error")
                and bool(str(info.get("title") or "").strip())
            )

            if valid:
                misses = 0
                _now_playing_queue_latest("media", dict(info))
                wait_seconds = 0.35
            else:
                misses += 1
                if misses >= 3:
                    _now_playing_queue_latest("clear", None)
                wait_seconds = 0.55

            if isinstance(info, dict) and info.get("error") and time.monotonic() - last_error_print >= 30.0:
                last_error_print = time.monotonic()
                try:
                    now_playing_log(f"[DETECTION_ERROR] {info.get('error')}")
                except Exception:
                    pass

            stop_event.wait(wait_seconds)
        except Exception as exc:
            try:
                now_playing_log(f"[MONITOR_ERROR] {exc}")
            except Exception:
                pass
            stop_event.wait(1.0)
'''

NOW_PUMP = r'''
def now_playing_ui_pump():
    global now_playing_last_key
    global now_playing_current_key
    global now_playing_monitor_last_info
    global now_playing_monitor_last_seen
    global now_playing_ui_pump_job

    now_playing_ui_pump_job = None

    if globals().get("now_playing_app_closing", False):
        return

    stop_event = globals().get("now_playing_monitor_stop")
    if stop_event is not None and stop_event.is_set():
        return
    if not _neto_v25_root_alive():
        return

    latest = None
    q = globals().get("now_playing_monitor_queue")
    if q is not None:
        try:
            while True:
                latest = q.get_nowait()
        except queue.Empty:
            pass
        except Exception:
            latest = None

    if latest is not None:
        try:
            kind, info, event_time = latest

            if kind == "media" and isinstance(info, dict):
                key = now_playing_info_key(info)
                previous_key = globals().get("now_playing_last_key")
                now_playing_monitor_last_info = info
                now_playing_monitor_last_seen = event_time

                try:
                    now_playing_sidebar_guncelle(info)
                except (tk.TclError, RuntimeError, AttributeError):
                    pass
                except Exception as exc:
                    try:
                        now_playing_log(f"[SIDEBAR_UPDATE_ERROR] {exc}")
                    except Exception:
                        pass

                try:
                    overlay_alive = bool(now_playing_overlay_alive())
                except Exception:
                    overlay_alive = False

                if overlay_alive:
                    try:
                        now_playing_overlay_update(info)
                    except (tk.TclError, RuntimeError, AttributeError):
                        pass
                    except Exception:
                        pass

                if key:
                    now_playing_current_key = key
                    now_playing_last_key = key

                if key and key != previous_key:
                    try:
                        should_open = bool(now_playing_auto_fullscreen_enabled()) and not bool(now_playing_overlay_alive())
                    except Exception:
                        should_open = False

                    if should_open:
                        try:
                            now_playing_overlay_goster(info, force=False)
                        except (tk.TclError, RuntimeError, AttributeError):
                            pass
                        except Exception:
                            pass

            elif kind == "clear":
                now_playing_monitor_last_info = None
                now_playing_monitor_last_seen = 0.0
                now_playing_last_key = None
                now_playing_current_key = None

                try:
                    now_playing_sidebar_guncelle(None)
                except (tk.TclError, RuntimeError, AttributeError):
                    pass
                except Exception:
                    pass

                try:
                    overlay_alive = bool(now_playing_overlay_alive())
                except Exception:
                    overlay_alive = False

                if overlay_alive:
                    empty_info = {
                        "title": now_playing_text("no_track"),
                        "artist": now_playing_text("not_found"),
                        "album": "",
                        "publisher": "NetOps",
                        "app": "Windows Media Session",
                        "source": "monitor",
                        "playback_status": "stopped",
                    }
                    try:
                        now_playing_overlay_update(empty_info)
                    except (tk.TclError, RuntimeError, AttributeError):
                        pass
                    except Exception:
                        pass
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        except Exception as exc:
            try:
                now_playing_log(f"[UI_PUMP_ERROR] {exc}")
            except Exception:
                pass

    if (
        not globals().get("now_playing_app_closing", False)
        and (stop_event is None or not stop_event.is_set())
        and _neto_v25_root_alive()
    ):
        now_playing_ui_pump_job = _neto_v25_safe_after(
            120,
            now_playing_ui_pump,
            owner=globals().get("root"),
        )
'''

NOW_START = r'''
def now_playing_monitor_baslat():
    global now_playing_monitor_started
    global now_playing_monitor_thread
    global now_playing_ui_pump_job

    if globals().get("now_playing_app_closing", False):
        return False
    if not _neto_v25_root_alive():
        return False

    try:
        existing = globals().get("now_playing_monitor_thread")
        if existing is not None and existing.is_alive():
            now_playing_monitor_started = True
            if not globals().get("now_playing_ui_pump_job"):
                now_playing_ui_pump_job = _neto_v25_safe_after(
                    0,
                    now_playing_ui_pump,
                    owner=globals().get("root"),
                )
            return True

        stop_event = globals().get("now_playing_monitor_stop")
        if stop_event is None:
            stop_event = threading.Event()
            globals()["now_playing_monitor_stop"] = stop_event
        stop_event.clear()

        now_playing_monitor_thread = threading.Thread(
            target=now_playing_monitor_loop,
            name="NetoNowPlayingMonitor",
            daemon=False,
        )
        now_playing_monitor_thread.start()
        now_playing_monitor_started = True

        if not globals().get("now_playing_ui_pump_job"):
            now_playing_ui_pump_job = _neto_v25_safe_after(
                80,
                now_playing_ui_pump,
                owner=globals().get("root"),
            )

        print("[NOW_PLAYING] güvenli izleyici başladı", flush=True)
        return True
    except Exception as exc:
        now_playing_monitor_started = False
        try:
            now_playing_log(f"[MONITOR_START_ERROR] {exc}")
        except Exception:
            pass
        return False
'''

NOW_STOP = r'''
def now_playing_monitor_durdur(wait_for_thread=True):
    global now_playing_monitor_started
    global now_playing_monitor_thread
    global now_playing_ui_pump_job

    stop_event = globals().get("now_playing_monitor_stop")
    try:
        if stop_event is not None:
            stop_event.set()
    except Exception:
        pass

    now_playing_monitor_started = False
    job = globals().get("now_playing_ui_pump_job")
    now_playing_ui_pump_job = None
    _neto_v25_cancel_after(job)

    thread_obj = globals().get("now_playing_monitor_thread")
    now_playing_monitor_thread = None
    if wait_for_thread and thread_obj is not None and thread_obj.is_alive() and thread_obj is not threading.current_thread():
        try:
            thread_obj.join(timeout=5.0)
        except Exception:
            pass

    q = globals().get("now_playing_monitor_queue")
    if q is not None:
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            pass
        except Exception:
            pass
'''

TITLE_START_WRAPPER = r'''
def _neto_titlebar_drag_start(event, *args, **kwargs):
    if not _neto_v25_root_alive():
        return "break"
    event_widget = getattr(event, "widget", None)
    if event_widget is not None and not _neto_v25_widget_alive(event_widget):
        return "break"
    try:
        return __ORIGINAL_NAME__(event, *args, **kwargs)
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        try:
            _neto_titlebar_state["drag_pending"] = False
            _neto_titlebar_state["drag_active"] = False
        except Exception:
            pass
        return "break"
    except Exception:
        return "break"
'''

TITLE_MOTION_WRAPPER = r'''
def _neto_titlebar_drag_motion(event, *args, **kwargs):
    if not _neto_v25_root_alive():
        return "break"
    event_widget = getattr(event, "widget", None)
    if event_widget is not None and not _neto_v25_widget_alive(event_widget):
        return "break"
    try:
        return __ORIGINAL_NAME__(event, *args, **kwargs)
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        try:
            _neto_titlebar_state["drag_pending"] = False
            _neto_titlebar_state["drag_active"] = False
        except Exception:
            pass
        return "break"
    except Exception:
        return "break"
'''

TITLE_END_WRAPPER = r'''
def _neto_titlebar_drag_end(event=None, *args, **kwargs):
    if event is not None:
        event_widget = getattr(event, "widget", None)
        if event_widget is not None and not _neto_v25_widget_alive(event_widget):
            return "break"
    try:
        return __ORIGINAL_NAME__(event, *args, **kwargs)
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        try:
            _neto_titlebar_state["drag_pending"] = False
            _neto_titlebar_state["drag_active"] = False
        except Exception:
            pass
        return "break"
    except Exception:
        return "break"
'''

SETTINGS_OPEN_WRAPPER = r'''
def ayarlar_sayfasi_ac(section="general", *args, **kwargs):
    if not _neto_v25_root_alive():
        return False

    controller = globals().get("settings_page_controller")
    if controller is not None:
        real_page = getattr(controller, "_real", None)
        surface = getattr(real_page, "surface", None) if real_page is not None else None
        if surface is not None and not _neto_v25_widget_alive(surface):
            try:
                controller._real = None
                controller._creating = False
            except Exception:
                pass

    try:
        return __ORIGINAL_NAME__(section, *args, **kwargs)
    except (tk.TclError, RuntimeError, AttributeError) as exc:
        if controller is not None:
            try:
                controller._real = None
                controller._creating = False
            except Exception:
                pass
        try:
            print(f"[SETTINGS_PAGE_WIDGET_DESTROYED] {exc}", flush=True)
        except Exception:
            pass
        return False
    except Exception as exc:
        try:
            print(f"[SETTINGS_PAGE_OPEN_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return False
'''


def remove_main_helper(text: str) -> str:
    return re.sub(
        rf"\n?{re.escape(HELPER_BEGIN)}.*?{re.escape(HELPER_END)}\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )


def insert_main_helper(text: str, filename: str) -> str:
    text = remove_main_helper(text)
    tree = parse(text, filename)
    imports = [
        n for n in tree.body
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno <= 180
    ]
    index = max((n.end_lineno for n in imports), default=0)
    lines = text.splitlines(keepends=True)
    lines[index:index] = ["\n" + MAIN_HELPERS.strip("\n") + "\n\n"]
    return "".join(lines)


def patch_close_protocol(text: str) -> str:
    pattern = re.compile(
        r'(?m)^(?P<indent>[ \t]*)(?P<root>[A-Za-z_][\w.]*)\.protocol\(\s*'
        r'(?P<quote>["\'])WM_DELETE_WINDOW(?P=quote)\s*,\s*'
        r'(?P<callback>[^\n\)]+)\s*\)\s*$'
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    match = matches[-1]
    callback = match.group("callback").strip()
    if callback == "_neto_v25_safe_close":
        return text
    indent = match.group("indent")
    root_name = match.group("root")
    replacement = (
        f"{indent}_NETO_V25_ORIGINAL_CLOSE = {callback}\n"
        f"{indent}{root_name}.protocol(\"WM_DELETE_WINDOW\", _neto_v25_safe_close)"
    )
    return text[:match.start()] + replacement + text[match.end():]


def patch_main(path: Path) -> dict:
    text = read_text(path)
    filename = str(path)

    if HELPER_BEGIN in text and "güvenli izleyici başladı" in text:
        return {"file": path.name, "status": "already_patched"}

    text = insert_main_helper(text, filename)
    text = replace_last_function(text, filename, "_now_playing_queue_latest", NOW_QUEUE)
    text = replace_last_function(text, filename, "now_playing_monitor_loop", NOW_LOOP)
    text = replace_last_function(text, filename, "now_playing_ui_pump", NOW_PUMP)
    text = replace_last_function(text, filename, "now_playing_monitor_baslat", NOW_START)

    if find_functions(text, filename, "now_playing_monitor_durdur"):
        text = replace_last_function(text, filename, "now_playing_monitor_durdur", NOW_STOP)
    else:
        node = find_functions(text, filename, "now_playing_monitor_baslat")[-1]
        lines = text.splitlines(keepends=True)
        lines[node.end_lineno:node.end_lineno] = ["\n" + indent_block(NOW_STOP, node.col_offset) + "\n"]
        text = "".join(lines)

    text = wrap_last_function(text, filename, "_neto_titlebar_drag_start", TITLE_START_WRAPPER)
    text = wrap_last_function(text, filename, "_neto_titlebar_drag_motion", TITLE_MOTION_WRAPPER, required=False)
    text = wrap_last_function(text, filename, "_neto_titlebar_drag_end", TITLE_END_WRAPPER, required=False)
    text = wrap_last_function(text, filename, "ayarlar_sayfasi_ac", SETTINGS_OPEN_WRAPPER)

    text = text.replace("exit_callback=root.destroy,", "exit_callback=_neto_v25_safe_close,")
    text = patch_close_protocol(text)
    parse(text, filename)
    write_text(path, text)
    return {"file": path.name, "status": "patched"}


SETTINGS_HELPERS = r'''
# NETO_SETTINGS_WIDGET_FIX_V25_BEGIN
def _neto_v25_settings_widget_alive(widget) -> bool:
    if widget is None:
        return False
    try:
        return bool(int(widget.winfo_exists()))
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        return False
    except Exception:
        return False


def _neto_v25_settings_cancel_jobs(page) -> None:
    page._neto_v25_generation = int(getattr(page, "_neto_v25_generation", 0)) + 1
    jobs = set(getattr(page, "_neto_v25_after_jobs", set()) or set())
    page._neto_v25_after_jobs = set()
    root_obj = getattr(page, "root", None)
    if not _neto_v25_settings_widget_alive(root_obj):
        return

    for job in jobs:
        try:
            root_obj.after_cancel(job)
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        except Exception:
            pass

    for name, value in tuple(vars(page).items()):
        if not isinstance(value, str):
            continue
        lower = name.lower()
        if not (lower.endswith("_job") or lower.endswith("_after") or lower.endswith("_after_id") or lower.endswith("_timer")):
            continue
        try:
            root_obj.after_cancel(value)
        except Exception:
            pass
        try:
            setattr(page, name, None)
        except Exception:
            pass
# NETO_SETTINGS_WIDGET_FIX_V25_END
'''

SETTINGS_SAFE_AFTER = r'''
def _neto_v25_safe_after(self, delay_ms, callback=None, *args):
    root_obj = getattr(self, "root", None)
    if not _neto_v25_settings_widget_alive(root_obj):
        return None
    if callback is None:
        try:
            return root_obj.after(delay_ms)
        except Exception:
            return None

    generation = int(getattr(self, "_neto_v25_generation", 0))
    jobs = getattr(self, "_neto_v25_after_jobs", None)
    if not isinstance(jobs, set):
        jobs = set()
        self._neto_v25_after_jobs = jobs

    holder = {"job": None}

    def guarded():
        job = holder.get("job")
        if job is not None:
            jobs.discard(job)
        if generation != int(getattr(self, "_neto_v25_generation", 0)):
            return
        if not _neto_v25_settings_widget_alive(root_obj):
            return
        surface = getattr(self, "surface", None)
        if surface is not None and not _neto_v25_settings_widget_alive(surface):
            return
        try:
            callback(*args)
        except (tk.TclError, RuntimeError, AttributeError):
            return
        except Exception:
            return

    try:
        job = root_obj.after(max(0, int(delay_ms)), guarded)
        holder["job"] = job
        jobs.add(job)
        return job
    except Exception:
        return None
'''

SETTINGS_SHOW = r'''
def show_section(self, section="general"):
    if not _neto_v25_settings_widget_alive(getattr(self, "root", None)):
        return False
    if not _neto_v25_settings_widget_alive(getattr(self, "surface", None)):
        return False
    if not _neto_v25_settings_widget_alive(getattr(self, "content", None)):
        return False

    self.section = section if section in {
        "general", "appearance", "netolab", "security", "updates", "about"
    } else "general"

    alive_buttons = {}
    for key, button in tuple(getattr(self, "nav_buttons", {}).items()):
        if not _neto_v25_settings_widget_alive(button):
            continue
        selected = key == self.section
        try:
            button.configure(
                fg_color=self.palette["accent"] if selected else "transparent",
                hover_color=self.palette["accent"] if selected else self.palette["hover"],
                text_color="#FFFFFF" if selected else self.palette["text"],
            )
            alive_buttons[key] = button
        except (tk.TclError, RuntimeError, AttributeError):
            continue
        except Exception:
            continue
    self.nav_buttons = alive_buttons

    try:
        self._clear(self.content)
    except (tk.TclError, RuntimeError, AttributeError):
        return False

    if not _neto_v25_settings_widget_alive(getattr(self, "content", None)):
        return False

    renderers = {
        "general": self._render_general,
        "appearance": self._render_appearance,
        "netolab": self._render_netolab,
        "security": self._render_security,
        "updates": self._render_updates,
        "about": self._render_about,
    }
    renderer = renderers.get(self.section)
    if renderer is None:
        return False
    try:
        renderer()
    except (tk.TclError, RuntimeError, AttributeError):
        return False

    try:
        canvas = getattr(self.content, "_parent_canvas", None)
        if _neto_v25_settings_widget_alive(canvas):
            canvas.yview_moveto(0)
    except Exception:
        pass
    return True
'''

SETTINGS_OPEN = r'''
def open(self, section="general"):
    if not _neto_v25_settings_widget_alive(getattr(self, "root", None)):
        return False
    if not _neto_v25_settings_widget_alive(getattr(self, "parent", None)):
        return False

    self.data = self._load()
    self.lang = self._language()
    self.palette = self._palette()
    self.section = section if section else "general"

    surface = getattr(self, "surface", None)
    if surface is not None and not _neto_v25_settings_widget_alive(surface):
        _neto_v25_settings_cancel_jobs(self)
        self.surface = None
        self.header = None
        self.body = None
        self.sidebar = None
        self.content_shell = None
        self.content = None
        self.nav_buttons = {}

    if callable(self.on_open):
        try:
            self.on_open()
        except (tk.TclError, RuntimeError, AttributeError):
            return False
        except Exception:
            pass

    try:
        if not _neto_v25_settings_widget_alive(getattr(self, "surface", None)):
            self._build()
        else:
            self.surface.pack(fill="both", expand=True)
    except (tk.TclError, RuntimeError, AttributeError):
        return False

    self.is_open = True
    if not self.show_section(self.section):
        return False

    try:
        if _neto_v25_settings_widget_alive(self.surface):
            self.surface.lift()
    except Exception:
        pass
    return True
'''

SETTINGS_CLOSE = r'''
def close(self):
    _neto_v25_settings_cancel_jobs(self)
    surface = getattr(self, "surface", None)
    if _neto_v25_settings_widget_alive(surface):
        try:
            surface.pack_forget()
        except Exception:
            pass
    self.is_open = False
    if callable(self.on_close):
        try:
            self.on_close()
        except Exception:
            pass
    return True
'''

SETTINGS_REFRESH_LANGUAGE = r'''
def refresh_language(self):
    self.lang = self._language()
    was_open = bool(getattr(self, "is_open", False))
    section = getattr(self, "section", "general")
    _neto_v25_settings_cancel_jobs(self)

    surface = getattr(self, "surface", None)
    if _neto_v25_settings_widget_alive(surface):
        try:
            surface.destroy()
        except Exception:
            pass

    self.surface = None
    self.header = None
    self.body = None
    self.sidebar = None
    self.content_shell = None
    self.content = None
    self.nav_buttons = {}

    if was_open:
        try:
            self._build()
        except (tk.TclError, RuntimeError, AttributeError):
            return False
        self.is_open = True
        return self.show_section(section)
    return True
'''

SETTINGS_REFRESH_THEME = r'''
def refresh_theme(self):
    self.data = self._load()
    self.palette = self._palette()
    was_open = bool(getattr(self, "is_open", False))
    section = getattr(self, "section", "general")
    _neto_v25_settings_cancel_jobs(self)

    surface = getattr(self, "surface", None)
    if _neto_v25_settings_widget_alive(surface):
        try:
            surface.destroy()
        except Exception:
            pass

    self.surface = None
    self.header = None
    self.body = None
    self.sidebar = None
    self.content_shell = None
    self.content = None
    self.nav_buttons = {}

    if was_open:
        try:
            self._build()
        except (tk.TclError, RuntimeError, AttributeError):
            return False
        self.is_open = True
        return self.show_section(section)
    return True
'''


def insert_settings_helper(text: str, filename: str) -> str:
    text = re.sub(
        rf"\n?{re.escape(SETTINGS_BEGIN)}.*?{re.escape(SETTINGS_END)}\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )
    tree = parse(text, filename)
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    index = max((n.end_lineno for n in imports), default=0)
    lines = text.splitlines(keepends=True)
    lines[index:index] = ["\n" + SETTINGS_HELPERS.strip("\n") + "\n\n"]
    return "".join(lines)


def insert_class_method(text: str, filename: str, class_name: str, method: str) -> str:
    tree = parse(text, filename)
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name]
    if not classes:
        raise RuntimeError(f"Sınıf bulunamadı: {class_name}")
    cls = classes[-1]
    lines = text.splitlines(keepends=True)
    lines[cls.end_lineno:cls.end_lineno] = ["\n" + indent_block(method, cls.col_offset + 4) + "\n"]
    return "".join(lines)


def patch_settings(path: Path) -> dict:
    text = read_text(path)
    filename = str(path)
    if SETTINGS_BEGIN in text and "alive_buttons" in text and "_neto_v25_safe_after" in text:
        return {"file": path.name, "status": "already_patched"}

    text = insert_settings_helper(text, filename)
    tree = parse(text, filename)
    if not any(isinstance(n, ast.FunctionDef) and n.name == "_neto_v25_safe_after" for n in ast.walk(tree)):
        text = insert_class_method(text, filename, "NetoSettingsPage", SETTINGS_SAFE_AFTER)

    text = text.replace("self.root.after(", "self._neto_v25_safe_after(")
    text = replace_last_function(text, filename, "show_section", SETTINGS_SHOW)
    text = replace_last_function(text, filename, "open", SETTINGS_OPEN)
    text = replace_last_function(text, filename, "close", SETTINGS_CLOSE)
    text = replace_last_function(text, filename, "refresh_language", SETTINGS_REFRESH_LANGUAGE)
    text = replace_last_function(text, filename, "refresh_theme", SETTINGS_REFRESH_THEME)

    parse(text, filename)
    write_text(path, text)
    return {"file": path.name, "status": "patched"}


def main() -> int:
    explicit = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else None
    project = find_project(explicit)
    main_file = find_main(project)
    settings_file = project / SETTINGS_NAME

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = project / f"NETO_V25_ONCESI_YEDEK_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    files = [main_file]
    if settings_file.is_file():
        files.append(settings_file)

    for file in files:
        shutil.copy2(file, backup_dir / file.name)

    report = {
        "version": VERSION,
        "project": str(project),
        "backup": str(backup_dir),
        "results": [],
    }

    try:
        report["results"].append(patch_main(main_file))
        if settings_file.is_file():
            report["results"].append(patch_settings(settings_file))
        else:
            report["results"].append({"file": SETTINGS_NAME, "status": "not_found_skipped"})

        for file in files:
            py_compile.compile(str(file), doraise=True)

        report["status"] = "success"
        (project / "NETO_V25_KURULUM_RAPORU.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (project / "NETO_V25_SON_YEDEK.txt").write_text(str(backup_dir), encoding="utf-8")

        log("")
        log("SONUC: BASARILI")
        log(f"Yedek: {backup_dir}")
        return 0
    except Exception as exc:
        for file in files:
            backup = backup_dir / file.name
            if backup.is_file():
                shutil.copy2(backup, file)

        report["status"] = "failed_rolled_back"
        report["error"] = repr(exc)
        try:
            (project / "NETO_V25_KURULUM_RAPORU.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        log("")
        log("SONUC: BASARISIZ - OTOMATIK GERI ALINDI")
        log(f"Hata: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
