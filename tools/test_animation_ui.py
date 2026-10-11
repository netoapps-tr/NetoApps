"""Exercise the actual NetOps UI with isolated data and disabled background services."""
import inspect
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "logs" / "animation_qa"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(OUT / "data")
os.environ["LOCALAPPDATA"] = str(OUT / "local")
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, str(PROJECT))
os.chdir(OUT)

import config
config.get_user_data_dir = lambda: str(OUT / "data")
Path(config.get_user_data_dir()).mkdir(parents=True, exist_ok=True)
config.FILE_PATH = config.get_data_path("hafiza.json")
Path(config.FILE_PATH).write_text(json.dumps({"dil": "tr", "start_live_mode_on_launch": False,
    "onboarding_completed": True}), encoding="utf-8")
import customtkinter as ctk
import tkinter as tk
from PIL import ImageGrab
from neto_motion_engine_v2 import get_motion_engine

# UI tests do not start ADB, microphones, schedulers, browsers or network workers.
threading.Thread.start = lambda self: None
import subprocess
class NoChild(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        raise OSError("Background processes are disabled by the UI test")
subprocess.Popen = NoChild
import webbrowser
webbrowser.open = lambda *args, **kwargs: False

original_loop = ctk.CTk.mainloop
report = {"checks": [], "callback_errors": [], "frame_gaps_ms": []}


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def test_loop(root, *args, **kwargs):
    scope = inspect.currentframe().f_back.f_globals
    scope["sesli_oku"] = lambda *a, **k: None
    scope["ses_oynat"] = lambda *a, **k: None
    scope["NETO_START_TIME_FOR_STARTUP_FIX"] = time.time() - 20
    def error(*exc):
        report["callback_errors"].append("".join(traceback.format_exception(*exc)))
    root.report_callback_exception = error
    engine = get_motion_engine(root)
    controller = scope["settings_page_controller"]
    report["entered_mainloop"] = True
    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
    def snap(name):
        root.lift()
        root.update_idletasks()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height())).save(OUT / (name + ".png"))
    def gate_start():
        found = [w for w in descendants(root) if isinstance(w, ctk.CTkButton)
                 and str(w.cget("text")).strip().lower() in ("başlat", "start")]
        check("gate_start_button", bool(found))
        if found:
            found[-1].invoke()
    def ready():
        if root.state() != "normal":
            root.after(250, ready)
            return
        check("main_visible_after_gate", True)
        check("jelly_intro_started", bool(scope.get("_neto_motion_v147", {}).get("jelly_ran")))
        root.geometry("1040x740+40+40")
        scope["_neto_bind_hover_tree"]()
        button = scope["btn_gonder"]
        report["button_shape_before"] = {k: button.cget(k) for k in ("width","height","corner_radius","border_width")}
        report["button_base_before"] = button.cget("fg_color")
        for i in range(20):
            root.after(i * 15, lambda i=i: button._neto_hover_controller.set_hovered(i % 2 == 0))
        root.after(330, lambda: button._neto_hover_controller.set_hovered(False))
        root.after(800, check_hover)
        root.after(1000, menu_test)
        root.after(2800, check_menu)
        root.after(3100, open_settings)
        root.after(4100, check_settings)
        root.after(4400, check_settings_reversed)
        root.after(4480, check_sidebar_reveal_start)
        root.after(5000, check_sidebar_reveal_done)
        root.after(5200, chat_test)
        root.after(6000, check_chat)
        root.after(6700, check_small)
        root.after(7400, finish)
    def check_hover():
        b = scope["btn_gonder"]
        check("hover_preserves_shape", report["button_shape_before"] == {k: b.cget(k) for k in report["button_shape_before"]})
        check("hover_returns_to_base", b.cget("fg_color") == report["button_base_before"])
    def menu_test():
        scope["_sidebar_layout_uygula"](False)
        root.after(70, lambda: scope["_sidebar_layout_uygula"](True))
    def check_menu():
        motion_job = engine._jobs.get("sidebar-width")
        report["sidebar_diag"] = {
            "compact": scope["sidebar_state"]["compact"],
            "current_width": scope["sidebar_state"]["current_width"],
            "panel_width": scope["PANEL_WIDTH"],
            "compact_width": scope["sidebar_compact_width"],
            "animating": scope["sidebar_state"]["animating"],
            "job": scope["sidebar_state"]["job"],
            "motion_elapsed_ms": (
                round((time.perf_counter() - motion_job["started"]) * 1000, 1)
                if motion_job else None
            ),
            "motion_duration_ms": (
                round(motion_job["duration"] * 1000, 1)
                if motion_job else None
            ),
        }
        check("sidebar_open_after_rapid_reverse",
              not scope["sidebar_state"]["compact"]
              and scope["sidebar_state"]["current_width"] in {
                  scope["PANEL_WIDTH"], scope["sidebar_compact_width"]
              })
        check("sidebar_animation_finishes", not scope["sidebar_state"]["animating"])
    def open_settings():
        scope["_neto_settings_page_open"]("general")
        report["first_surface_id"] = id(controller.surface)
    def check_settings():
        check("settings_visible", controller.is_open and controller.surface.winfo_manager() == "place")
        check("settings_at_rest", float(controller.surface.place_info().get("y", -1)) == 0)
        snap("settings")
        scope["_neto_settings_page_close"]()
        root.after(55, lambda: scope["_neto_settings_page_open"]("general"))
    def check_settings_reversed():
        check("settings_reused", id(controller.surface) == report["first_surface_id"])
        check("settings_still_open_after_reverse", controller.surface.winfo_viewable())
        check("settings_not_closing", not scope["_settings_theme_state"]["closing"])
        controller._real.show_section("about")
        controller._real.show_section("general")
        scope["_neto_settings_page_close"]()

    def check_sidebar_reveal_start():
        desktop = root.winfo_width() >= scope["MINI_LIMIT"]
        side_panel = scope["side_panel"]
        check(
            "settings_close_starts_sidebar_offscreen",
            not desktop
            or (side_panel.winfo_manager() == "place" and side_panel.winfo_x() <= 0),
        )

    def check_sidebar_reveal_done():
        desktop = root.winfo_width() >= scope["MINI_LIMIT"]
        side_panel = scope["side_panel"]
        check(
            "settings_close_finishes_sidebar_reveal",
            not desktop or side_panel.winfo_manager() == "pack",
        )
    def chat_test():
        check("settings_closed", not controller.is_open)
        scope["_neto_sohbet_balonu_ekle"]("Animasyon testi", "user")
        scope["_neto_sohbet_balonu_ekle"]("Mesaj çubuğu sabit, sohbet alanı açık.", "assistant")
        scope["_neto_iddiali_intro_baslat"](force=True)
    def check_chat():
        check("logo_stays_hidden_in_chat", not scope["gif_ana_label"].winfo_manager())
        inp, chat = scope["input_container"], scope["chat_container"]
        check("input_visible", inp.winfo_manager() == "pack" and inp.winfo_height() >= 42)
        check("chat_above_input", chat.winfo_y() + chat.winfo_height() <= inp.winfo_y() + 2)
        snap("chat")
        root.geometry("650x620+40+40")
    def check_small():
        inp = scope["input_container"]
        check("small_input_visible", inp.winfo_manager() == "pack" and inp.winfo_height() >= 42)
        snap("small")
    heartbeat = [time.perf_counter()]
    def pulse():
        now = time.perf_counter()
        report["frame_gaps_ms"].append(round((now-heartbeat[0])*1000, 2))
        heartbeat[0] = now
        root.after(16, pulse)
    def finish():
        report["engine_errors"] = engine.errors
        report["passed"] = all(c["passed"] for c in report["checks"]) and not report["callback_errors"] and not engine.errors
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ANIMATION_QA", report["passed"], report["checks"], flush=True)
        root.destroy()
    # The launch gate is built asynchronously after the main UI. Keep each
    # assertion behind the previous transition so the test measures the UI,
    # not a race between the gate and its first frame.
    root.after(1600, gate_start)
    root.after(6500, ready)
    root.after(3300, pulse)
    original_loop(root, *args, **kwargs)


ctk.CTk.mainloop = test_loop
sys.argv = [str(PROJECT / "asistan beta.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
if not (OUT / "report.json").exists():
    raise SystemExit("UI test did not reach completion")
result = json.loads((OUT / "report.json").read_text(encoding="utf-8"))
raise SystemExit(0 if result["passed"] else 1)
