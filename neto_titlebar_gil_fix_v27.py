#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import py_compile
import shutil
import sys
import time
from pathlib import Path

MAIN_NAMES = ("asistan beta.py", "asistan_beta.py")
VERSION = "27.0"


def find_project(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path.cwd())
    desktop = Path.home() / "Desktop"
    candidates.extend((
        desktop / "NETO ASİSTAN SİLME",
        desktop / "NETO ASISTAN SILME",
    ))

    for candidate in candidates:
        try:
            candidate = candidate.expanduser().resolve()
        except Exception:
            continue
        if any((candidate / name).is_file() for name in MAIN_NAMES):
            return candidate
    raise FileNotFoundError(
        "NetOps proje klasörü bulunamadı. KUR_V27.bat dosyasını "
        "asistan beta.py bulunan klasörde çalıştır."
    )


def find_main(project: Path) -> Path:
    for name in MAIN_NAMES:
        path = project / name
        if path.is_file():
            return path
    raise FileNotFoundError("asistan beta.py bulunamadı.")


def read_source(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def find_function(source: str, filename: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source, filename=filename)
    nodes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if not nodes:
        raise RuntimeError(f"Fonksiyon bulunamadı: {name}")
    return sorted(nodes, key=lambda n: (n.lineno, n.col_offset))[-1]


def indent(code: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else "" for line in code.strip("\n").splitlines())


def replace_function(source: str, filename: str, name: str, code: str) -> str:
    node = find_function(source, filename, name)
    lines = source.splitlines(keepends=True)
    replacement = indent(code, node.col_offset) + "\n"
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    result = "".join(lines)
    ast.parse(result, filename=filename)
    return result


DRAG_START = r'''
def _neto_titlebar_drag_start(event):
    # Native pencere sürüklemesini GIL-safe ve re-entry-safe başlatır.
    try:
        if root is None or not bool(int(root.winfo_exists())):
            return "break"

        event_widget = getattr(event, "widget", None)
        if event_widget is not None:
            try:
                if not bool(int(event_widget.winfo_exists())):
                    return "break"
            except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
                return "break"

        _neto_titlebar_state["drag_x"] = int(event.x_root - root.winfo_x())
        _neto_titlebar_state["drag_y"] = int(event.y_root - root.winfo_y())

    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        return "break"
    except Exception as exc:
        try:
            print(f"[TITLEBAR_DRAG_PREPARE_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return "break"

    if os.name != "nt":
        return None

    try:
        hwnd = int(_neto_titlebar_hwnd() or 0)
    except Exception:
        hwnd = 0

    if not hwnd:
        return None

    try:
        old_job = _neto_titlebar_state.pop("native_drag_job", None)
        if old_job:
            root.after_cancel(old_job)
    except (tk.TclError, RuntimeError, AttributeError):
        pass
    except Exception:
        pass

    def _neto_begin_native_drag(target_hwnd=hwnd):
        _neto_titlebar_state["native_drag_job"] = None

        try:
            if root is None or not bool(int(root.winfo_exists())):
                return

            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)

            release_capture = user32.ReleaseCapture
            release_capture.argtypes = ()
            release_capture.restype = wintypes.BOOL

            post_message = user32.PostMessageW
            post_message.argtypes = (
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )
            post_message.restype = wintypes.BOOL

            # SendMessageW kullanılmaz. Senkron çağrı ctypes GIL'i bırakmışken
            # pencere prosedüründen Tk/Python'a yeniden giriş yapabiliyordu.
            release_capture()
            posted = bool(post_message(target_hwnd, 0x00A1, 2, 0))

            if not posted:
                error_code = ctypes.get_last_error()
                try:
                    print(
                        f"[TITLEBAR_POST_MESSAGE_ERROR] winerror={error_code}",
                        flush=True,
                    )
                except Exception:
                    pass

        except (tk.TclError, RuntimeError, AttributeError):
            return
        except Exception as exc:
            try:
                print(f"[TITLEBAR_NATIVE_DRAG_ERROR] {exc}", flush=True)
            except Exception:
                pass

    try:
        # Mevcut Tk callback'i bittikten sonra asenkron Windows mesajı gönderilir.
        _neto_titlebar_state["native_drag_job"] = root.after_idle(
            _neto_begin_native_drag
        )
        return "break"
    except (tk.TclError, RuntimeError, AttributeError):
        return "break"
    except Exception as exc:
        try:
            print(f"[TITLEBAR_DRAG_SCHEDULE_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return "break"
'''


WINDOW_REDRAW = r'''
def _neto_window_redraw(enable=True):
    # Tema yenilemesini senkron SendMessageW kullanmadan güvenli tamamlar.
    if os.name != "nt":
        return

    try:
        if root is None or not bool(int(root.winfo_exists())):
            return
    except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
        return

    # WM_SETREDRAW kapatma yalnızca görsel optimizasyondu. Senkron native
    # callback riskini kaldırmak için kapatma aşaması no-op yapılır.
    if not enable:
        _neto_tema_refresh_state["redraw_suspended"] = True
        return

    _neto_tema_refresh_state["redraw_suspended"] = False

    def _redraw_now():
        try:
            if root is None or not bool(int(root.winfo_exists())):
                return

            import ctypes
            from ctypes import wintypes

            hwnd = int(root.winfo_id())
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            redraw_window = user32.RedrawWindow
            redraw_window.argtypes = (
                wintypes.HWND,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.UINT,
            )
            redraw_window.restype = wintypes.BOOL

            RDW_INVALIDATE = 0x0001
            RDW_UPDATENOW = 0x0100
            RDW_ALLCHILDREN = 0x0080
            redraw_window(
                hwnd,
                None,
                None,
                RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN,
            )

        except (tk.TclError, RuntimeError, AttributeError):
            return
        except Exception as exc:
            try:
                print(f"[WINDOW_REDRAW_ERROR] {exc}", flush=True)
            except Exception:
                pass

    try:
        root.after_idle(_redraw_now)
    except (tk.TclError, RuntimeError, AttributeError):
        pass
    except Exception:
        pass
'''


def patch(path: Path) -> dict:
    source = read_source(path)
    original = source

    source = replace_function(
        source, str(path), "_neto_titlebar_drag_start", DRAG_START
    )
    source = replace_function(
        source, str(path), "_neto_window_redraw", WINDOW_REDRAW
    )

    if "ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)" in source:
        raise RuntimeError("Tehlikeli titlebar SendMessageW çağrısı kaldı.")

    ast.parse(source, filename=str(path))
    path.write_text(source, encoding="utf-8", newline="\n")
    py_compile.compile(str(path), doraise=True)

    return {
        "changed": source != original,
        "titlebar_sendmessage_removed": (
            "ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)" not in source
        ),
        "postmessage_installed": "post_message(target_hwnd, 0x00A1, 2, 0)" in source,
        "redraw_sendmessage_removed": "WM_SETREDRAW, 1 if enable else 0" not in source,
    }


def main() -> int:
    explicit = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else None
    project = find_project(explicit)
    main_file = find_main(project)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = project / f"NETO_V27_ONCESI_YEDEK_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_file = backup_dir / main_file.name
    shutil.copy2(main_file, backup_file)

    report = {
        "version": VERSION,
        "project": str(project),
        "file": str(main_file),
        "backup": str(backup_dir),
    }

    try:
        report.update(patch(main_file))
        report["status"] = "success"
        (project / "NETO_V27_SON_YEDEK.txt").write_text(
            str(backup_dir), encoding="utf-8"
        )
        (project / "NETO_V27_KURULUM_RAPORU.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print("")
        print("SONUC: BASARILI")
        print(f"Proje: {project}")
        print(f"Yedek: {backup_dir}")
        print("SendMessageW titlebar çağrısı kaldırıldı.")
        print("Native sürükleme after_idle + PostMessageW ile değiştirildi.")
        print("Python derleme testi geçti.")
        return 0

    except Exception as exc:
        shutil.copy2(backup_file, main_file)
        report["status"] = "failed_rolled_back"
        report["error"] = repr(exc)
        try:
            (project / "NETO_V27_KURULUM_RAPORU.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        print("")
        print("SONUC: BASARISIZ - OTOMATIK GERI ALINDI")
        print(f"Hata: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
