# =========================================================
# NETO CRASH GUARD v10.21
# Sessiz kapanmaları loglar, Tkinter callback hatalarını yakalar.
# =========================================================
import os
import sys
import time
import traceback
import faulthandler
import threading
import atexit

from config import get_user_data_dir

LOG_DIR = os.path.join(get_user_data_dir(), "logs")
CRASH_LOG = os.path.join(LOG_DIR, "crash.log")
LAST_LOG = os.path.join(LOG_DIR, "last_run.log")

def _ensure_logs():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass

def log(message):
    try:
        _ensure_logs()
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except Exception:
        pass

def last(message):
    try:
        _ensure_logs()
        with open(LAST_LOG, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except Exception:
        pass

def install(app_name="NetOps"):
    _ensure_logs()
    last("=" * 60)
    last(f"{app_name} start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    last(f"python: {sys.version}")
    last(f"exe: {sys.executable}")
    last(f"argv: {sys.argv}")

    try:
        fault_path = os.path.join(LOG_DIR, "fault.log")
        fault_file = open(fault_path, "a", encoding="utf-8")
        faulthandler.enable(file=fault_file, all_threads=True)
        last("faulthandler enabled")
    except Exception as e:
        log(f"[FAULT_HANDLER_INSTALL_ERROR] {e}")

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log("\n[SYS_EXCEPTHOOK]\n" + text)
        try:
            print(text, flush=True)
        except Exception:
            pass

    sys.excepthook = excepthook

    try:
        def thread_hook(args):
            text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
            log("\n[THREAD_EXCEPTHOOK]\n" + text)
            try:
                print(text, flush=True)
            except Exception:
                pass
        threading.excepthook = thread_hook
    except Exception:
        pass

    def on_exit():
        last(f"{app_name} exit: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    atexit.register(on_exit)
    install_exit_hooks()

def install_tk(root):
    try:
        def tk_report_callback_exception(exc, val, tb):
            text = "".join(traceback.format_exception(exc, val, tb))
            log("\n[TK_CALLBACK_EXCEPTION]\n" + text)
            try:
                print(text, flush=True)
            except Exception:
                pass
        root.report_callback_exception = tk_report_callback_exception
        last("tk report_callback_exception installed")
    except Exception as e:
        log(f"[TK_HOOK_INSTALL_ERROR] {e}")

BOOT_TRACE_LOG = os.path.join(LOG_DIR, "boot_trace.log")

def boot(step):
    try:
        _ensure_logs()
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {step}"
        with open(BOOT_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        try:
            print(f"[BOOT] {step}", flush=True)
        except Exception:
            pass
    except Exception:
        pass

def install_exit_hooks():
    try:
        _old_sys_exit = sys.exit
        def _logged_sys_exit(code=0):
            boot(f"sys.exit called with code={code}")
            return _old_sys_exit(code)
        sys.exit = _logged_sys_exit
    except Exception as e:
        log(f"[SYS_EXIT_HOOK_ERROR] {e}")

    try:
        _old_os_exit = os._exit
        def _logged_os_exit(code=0):
            boot(f"os._exit called with code={code}")
            try:
                log(f"[OS_EXIT] code={code}")
            except Exception:
                pass
            return _old_os_exit(code)
        os._exit = _logged_os_exit
    except Exception as e:
        log(f"[OS_EXIT_HOOK_ERROR] {e}")
