from __future__ import annotations

import asyncio
import concurrent.futures
import math
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageTk, ImageSequence
except Exception:
    Image = ImageTk = ImageSequence = None

try:
    import pygame

    PYGAME_OK = True
except Exception:
    pygame = None
    PYGAME_OK = False

from config import *

try:
    from lang import T
except Exception:

    def T(key: str, **kwargs) -> str:
        return str(
            {
                "live_starting": "Starting...",
                "live_mic_waiting": "Microphone: Waiting",
                "live_voice": "Voice: Local Piper Turkish Male",
                "live_start": "Start",
                "live_stop": "Stop",
                "live_closed": "Closed",
                "live_back_title": "NetOps Live",
                "live_back_msg": "Do you want to return to Assistant?\n\nLive Mode will close and NetOps will open.",
            }.get(key, key)
        )

import neto_ai
import neto_live_commands
import neto_live_mode

ctk.set_appearance_mode("dark")

LIVE_BG = "#000000"
LIVE_CARD = "#111111"
LIVE_TEXT = "#FFFFFF"
LIVE_DIM = "#8A8FA3"
LIVE_NEON = "#6E4CFF"
LIVE_RED = "#E33131"


def live_log(metin):
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "live_error.log"), "a", encoding="utf-8") as f:
            f.write(str(metin) + "\n")
    except Exception:
        pass


class NetoLiveApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("NetOps Live v10.35")
        self.root.geometry("500x720")
        self.root.minsize(420, 600)
        self.root.configure(fg_color=LIVE_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.back_to_assistant)

        self.live_controller = None
        self.gif_frames: list[object] = []
        self.gif_delays: list[int] = []
        self.gif_index = 0
        self.gif_job = None
        self.wave_job = None
        self.splash_job = None
        self.wave_canvas = None
        self.wave_bars: list[int] = []
        self.wave_layout: list[tuple[int, int]] = []
        self.wave_i = 0
        self._animation_epoch = 0
        self._tts_warm_started = False

        self.status_var = tk.StringVar(value=T("live_starting"))
        self.mic_var = tk.StringVar(value=T("live_mic_waiting"))
        self.voice_var = tk.StringVar(value=T("live_voice"))
        self.last_heard_var = tk.StringVar(value="")
        self.last_answer_var = tk.StringVar(value="")

        try:
            if PYGAME_OK and pygame is not None:
                pygame.mixer.init()
        except Exception:
            pass

        self.show_splash()
        self.root.after(1200, self._warm_tts)

    def _widget_alive(self, widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    def _cancel_job(self, attr_name):
        job = getattr(self, attr_name, None)
        if not job:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        setattr(self, attr_name, None)

    def _stop_animation_jobs(self):
        self._animation_epoch += 1
        self._cancel_job("gif_job")
        self._cancel_job("wave_job")
        self._cancel_job("splash_job")

    def _blend_color(self, start, end, progress):
        try:
            s = str(start).lstrip("#")
            e = str(end).lstrip("#")
            sr, sg, sb = [int(s[i : i + 2], 16) for i in (0, 2, 4)]
            er, eg, eb = [int(e[i : i + 2], 16) for i in (0, 2, 4)]
            p = max(0.0, min(1.0, float(progress)))
            return "#%02X%02X%02X" % (
                round(sr + (er - sr) * p),
                round(sg + (eg - sg) * p),
                round(sb + (eb - sb) * p),
            )
        except Exception:
            return str(end)

    def play_open_sound(self):
        try:
            if PYGAME_OK and pygame is not None:
                path = LIVE_OPEN_SOUND if "LIVE_OPEN_SOUND" in globals() else get_asset_path("denielcz-done-463074.mp3")
                if path and os.path.exists(path):
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(0.45)
                    sound.play()
        except Exception as e:
            print("[LIVE_APP] sound", e, flush=True)

    def _warm_tts(self):
        if self._tts_warm_started:
            return
        self._tts_warm_started = True

        def worker():
            try:
                from neto_anyspeech_tts import preload_voice as anyspeech_preload_voice

                anyspeech_preload_voice(logger=lambda msg: print(f"[LIVE][TTS_WARMUP] {msg}", flush=True))
            except Exception as e:
                print("[LIVE][TTS_WARMUP_ERR]", e, flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def load_gif(self, size=(380, 380)):
        self.gif_frames = []
        self.gif_delays = []
        if not Image or not ImageTk or not ImageSequence:
            return
        try:
            path = LIVE_GIF_PATH if "LIVE_GIF_PATH" in globals() else get_asset_path("Neto.gif")
            with Image.open(path) as img:
                for frame in ImageSequence.Iterator(img):
                    converted = frame.convert("RGBA")
                    converted.thumbnail(size, Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(converted.copy()))
                    delay = int(frame.info.get("duration", img.info.get("duration", 45)) or 45)
                    self.gif_delays.append(max(24, min(160, delay)))
        except Exception as e:
            print("[LIVE_APP] gif", e, flush=True)

    def animate_gif(self, label, token=None):
        try:
            token = self._animation_epoch if token is None else token
            if token != self._animation_epoch or not self._widget_alive(label):
                return
            delay = 45
            if self.gif_frames:
                index = self.gif_index % len(self.gif_frames)
                label.configure(image=self.gif_frames[index], text="")
                self.gif_index += 1
                if index < len(self.gif_delays):
                    delay = self.gif_delays[index]
            if token == self._animation_epoch and self._widget_alive(label):
                self.gif_job = self.root.after(delay, lambda: self.animate_gif(label, token=token))
        except Exception:
            self.gif_job = None

    def animate_wave(self, token=None):
        try:
            token = self._animation_epoch if token is None else token
            if token != self._animation_epoch:
                return
            canvas = self.wave_canvas
            if not self._widget_alive(canvas) or not self.wave_bars:
                return

            baseline = 72
            max_height = 52
            running = bool(self.live_controller and self.live_controller.is_running())
            phase_speed = 0.42 if running else 0.24
            amplitude_bias = 0.18 if running else 0.10
            self.wave_i += 1

            for index, item in enumerate(self.wave_bars):
                x1, x2 = self.wave_layout[index]
                phase = (self.wave_i * phase_speed) + (index * 0.58)
                pulse = (math.sin(phase) + 1.0) / 2.0
                pulse = max(0.0, min(1.0, pulse * (0.82 + (0.18 if index in (3, 4) else 0.0))))
                height = 12 + int(max_height * (amplitude_bias + (pulse * (1.0 - amplitude_bias))))
                top = baseline - height
                canvas.coords(item, x1, top, x2, baseline)
                canvas.itemconfigure(item, fill=self._blend_color("#27456F", LIVE_NEON, pulse))

            self.wave_job = self.root.after(72, lambda: self.animate_wave(token=token))
        except Exception:
            self.wave_job = None

    def show_splash(self):
        self._stop_animation_jobs()
        token = self._animation_epoch

        for widget in list(self.root.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass

        self.play_open_sound()
        frame = ctk.CTkFrame(self.root, fg_color=LIVE_BG)
        frame.pack(fill="both", expand=True)
        label = tk.Label(frame, bg=LIVE_BG, bd=0, highlightthickness=0)
        label.pack(expand=True)
        ctk.CTkLabel(frame, text="NETOPS LIVE", text_color=LIVE_TEXT, font=("Segoe UI Semibold", 24)).pack(pady=(0, 44))

        self.gif_index = 0
        self.load_gif((430, 430))
        self.animate_gif(label, token=token)
        self.splash_job = self.root.after(2200, lambda token=token: self.show_live_screen(token))

    def show_live_screen(self, token=None):
        if token is not None and token != self._animation_epoch:
            return

        self._cancel_job("splash_job")
        self._cancel_job("gif_job")
        self._cancel_job("wave_job")

        for widget in list(self.root.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass

        outer = ctk.CTkFrame(self.root, fg_color=LIVE_BG)
        outer.pack(fill="both", expand=True)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 0))
        ctk.CTkLabel(top, text="NETO LIVE", text_color=LIVE_TEXT, font=("Segoe UI Semibold", 24)).pack(side="left")
        ctk.CTkButton(
            top,
            text="X",
            width=42,
            height=36,
            corner_radius=12,
            fg_color=LIVE_CARD,
            hover_color="#222",
            text_color=LIVE_TEXT,
            command=self.back_to_assistant,
        ).pack(side="right")

        center = ctk.CTkFrame(outer, fg_color="transparent")
        center.pack(expand=True)

        self.logo_label = tk.Label(center, bg=LIVE_BG, bd=0, highlightthickness=0)
        self.logo_label.pack(pady=(0, 8))
        self.gif_index = 0
        self.load_gif((320, 320))
        self.animate_gif(self.logo_label, token=token)

        ctk.CTkLabel(center, textvariable=self.status_var, text_color=LIVE_NEON, font=("Segoe UI Semibold", 18)).pack(pady=(0, 8))

        self.wave_canvas = tk.Canvas(center, width=286, height=86, bg=LIVE_BG, bd=0, highlightthickness=0)
        self.wave_canvas.pack(pady=(0, 10))
        self.wave_canvas.create_line(16, 72, 270, 72, fill="#16315D", width=2)
        self.wave_bars = []
        self.wave_layout = []
        self.wave_i = 0
        bar_count = 8
        bar_width = 14
        gap = 12
        baseline = 72
        total_width = bar_count * bar_width + (bar_count - 1) * gap
        start_x = max(18, (286 - total_width) // 2)
        for index in range(bar_count):
            x1 = start_x + index * (bar_width + gap)
            x2 = x1 + bar_width
            self.wave_bars.append(
                self.wave_canvas.create_rectangle(x1, baseline - 12, x2, baseline, fill="#315B9C", outline="")
            )
            self.wave_layout.append((x1, x2))

        ctk.CTkLabel(center, textvariable=self.mic_var, text_color=LIVE_DIM, font=("Segoe UI", 13)).pack(pady=(0, 6))
        ctk.CTkLabel(center, textvariable=self.voice_var, text_color=LIVE_DIM, font=("Segoe UI", 12)).pack(pady=(0, 10))
        ctk.CTkLabel(center, textvariable=self.last_heard_var, text_color=LIVE_DIM, font=("Segoe UI", 12), wraplength=430).pack(pady=(0, 4))
        ctk.CTkLabel(center, textvariable=self.last_answer_var, text_color=LIVE_TEXT, font=("Segoe UI", 12), wraplength=430).pack(pady=(0, 16))

        buttons = ctk.CTkFrame(center, fg_color="transparent")
        buttons.pack()
        ctk.CTkButton(
            buttons,
            text=T("live_start"),
            width=160,
            height=46,
            corner_radius=18,
            fg_color="#FFF",
            text_color="#000",
            hover_color="#DDD",
            command=self.start_live,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons,
            text=T("live_stop"),
            width=160,
            height=46,
            corner_radius=18,
            fg_color=LIVE_RED,
            text_color="#FFF",
            hover_color="#B91F1F",
            command=self.stop_live,
        ).pack(side="left", padx=8)

        self.animate_wave(token=token)
        self.root.after(600, lambda token=token: self._start_live_if_current(token))

    def _start_live_if_current(self, token):
        if token != self._animation_epoch or not self._widget_alive(self.root):
            return
        self.start_live()

    def speak(self, text):
        threading.Thread(target=self._tts_worker, args=(str(text),), daemon=True).start()

    def _tts_worker(self, text):
        try:
            asyncio.run(self._tts_async(text))
        except Exception as e:
            print("[LIVE][TTS_ERR]", e, flush=True)
            live_log(f"[TTS_ERR] {e}")

    async def _tts_async(self, text):
        try:
            text = str(text).strip()
            if not text:
                return
            if len(text) > 700:
                text = text[:700] + "."
            from neto_anyspeech_tts import speak_text as anyspeech_speak_text

            await asyncio.to_thread(
                anyspeech_speak_text,
                text,
                logger=lambda msg: print(f"[LIVE][TTS] {msg}", flush=True),
            )
        except Exception as e:
            print("[LIVE][TTS_ASYNC]", e, flush=True)
            live_log(f"[TTS_ASYNC] {e}")

    def status(self, text):
        self.root.after(0, lambda: self.status_var.set(str(text)))

    def mic(self, text):
        self.root.after(0, lambda: self.mic_var.set(f"Mikrofon: {text}"))

    def transcript(self, text):
        print("[LIVE][DUYULAN]", text, flush=True)
        self.root.after(0, lambda: self.last_heard_var.set(f"Duyuldu: {text}"))

    def answer(self, text):
        print("[LIVE][CEVAP]", text, flush=True)
        s = str(text)
        s = s[:117] + "..." if len(s) > 120 else s
        self.root.after(0, lambda: self.last_answer_var.set(f"NetOps Agent: {s}"))

    def live_answer_engine(self, text):
        try:
            self.status("Komut kontrol ediliyor...")
            print("[LIVE][INPUT]", text, flush=True)

            try:
                cmd_answer = neto_live_commands.handle_live_command(text)
                if cmd_answer:
                    print("[LIVE][COMMAND_OUTPUT]", cmd_answer, flush=True)
                    return cmd_answer
            except Exception as ce:
                live_log(f"[COMMAND_ERR] {ce}")

            print("[LIVE][NETO_AGENT_INPUT]", text, flush=True)

            def _call_neto_agent():
                if hasattr(neto_ai, "neto_ai_cevap_ver"):
                    return neto_ai.neto_ai_cevap_ver(text)
                if hasattr(neto_ai, "_neto_ai_cevap_ver_core"):
                    return neto_ai._neto_ai_cevap_ver_core(text)
                return "NetOps Agent cevap fonksiyonu bulunamadi."

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_call_neto_agent)
                try:
                    ans = fut.result(timeout=23)
                except concurrent.futures.TimeoutError:
                    return "NetOps Agent 23 saniye icinde cevap veremedi. Daha kisa sorar misin?"

            if not ans:
                ans = "NetOps Agent cevap vermedi."

            print("[LIVE][NETO_AGENT_OUTPUT]", ans, flush=True)
            return ans
        except Exception as e:
            live_log(f"[NETO_AGENT_ERR] {e}\n{traceback.format_exc()}")
            return f"NetOps Agent baglanti hatasi: {e}"

    def start_live(self):
        try:
            if self.live_controller and self.live_controller.is_running():
                return
            self.last_heard_var.set("")
            self.last_answer_var.set("")
            self.live_controller = neto_live_mode.NetoLiveMode(
                answer_func=self.live_answer_engine,
                speak_func=self.speak,
                status_callback=self.status,
                transcript_callback=self.transcript,
                answer_callback=self.answer,
                mic_callback=self.mic,
                preferred_keywords=("AudioRelay", "Audio Relay", "WO Mic", "Microphone", "Mikrofon"),
                model_size="base",
                language="tr",
                record_seconds=4.5,
                sample_rate=16000,
                silence_threshold=0.004,
                tts_enabled=True,
            )
            self.live_controller.start()
        except Exception as e:
            live_log(f"[START_LIVE_ERR] {e}\n{traceback.format_exc()}")
            self.status(f"Hata: {e}")

    def stop_live(self):
        try:
            if self.live_controller:
                self.live_controller.stop()
            self.status_var.set(T("live_closed"))
            self.mic_var.set(T("live_mic_waiting"))
        except Exception:
            pass

    def back_to_assistant(self):
        try:
            if not messagebox.askyesno(T("live_back_title"), T("live_back_msg")):
                return
            self._stop_animation_jobs()
            self.stop_live()
            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if getattr(sys, "frozen", False):
                live_log("[BACK] frozen assistant baslatiliyor")
                subprocess.Popen([sys.executable], creationflags=flags)
            else:
                base = os.path.dirname(os.path.abspath(__file__))
                assistant_path = os.path.join(base, "asistan beta.py")
                live_log(f"[BACK] python assistant baslatiliyor: {assistant_path}")
                subprocess.Popen([sys.executable, assistant_path], creationflags=flags)
            self.root.destroy()
        except Exception as e:
            try:
                messagebox.showerror(T("live_back_title"), f"Geri donus hatasi:\n{e}")
            except Exception:
                pass

    def close(self):
        self.back_to_assistant()

    def run(self):
        self.root.mainloop()


def main():
    NetoLiveApp().run()


if __name__ == "__main__":
    main()
