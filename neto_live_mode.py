# =========================================================
# NETO LIVE MODE v5.0 - ISOLATED WORKER PROCESS
# AudioRelay / WO Mic / normal microphone -> Whisper -> NetOps Agent
#
# Native speech libraries run in a separate process. A DLL crash in
# torch/CTranslate2/faster-whisper can no longer close the NetOps UI process.
# =========================================================
from __future__ import annotations

import base64
import difflib
import faulthandler
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from pathlib import Path
from typing import Any, Callable, Optional

_EVENT_PREFIX = "NETO_LIVE_EVENT:"
_WORKER_EVENT_PATH: Optional[str] = None
_WORKER_EVENT_LOCK = threading.Lock()


def _local_log_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "NetoAssistant", "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _append_log(path: str, text: str) -> None:
    try:
        with open(path, "a", encoding="utf-8", errors="replace") as handle:
            handle.write(str(text).rstrip() + "\n")
    except Exception:
        pass


def _emit(event: str, **payload: Any) -> None:
    data = {"event": str(event), **payload}
    line = json.dumps(data, ensure_ascii=False)
    # File IPC is the source of truth. It also works in PyInstaller --windowed
    # builds where sys.stdout/sys.stdin can be None.
    if _WORKER_EVENT_PATH:
        try:
            with _WORKER_EVENT_LOCK:
                with open(_WORKER_EVENT_PATH, "a", encoding="utf-8", buffering=1) as handle:
                    handle.write(line + "\n")
        except Exception:
            pass
    try:
        print(_EVENT_PREFIX + line, flush=True)
    except Exception:
        pass


def _worker_clean_word(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""

    replacements = {
        "avuk": "tavuk", "avuk.": "tavuk", "avuk?": "tavuk",
        "evra": "kevra", "kevrağ": "kevra",
        "netto": "neto", "nato": "neto",
        "mikrafon": "mikrofon", "mikrafonu": "mikrofonu",
        "başalat": "başlat", "başlatı": "başlat",
        "yutub": "youtube", "yutüp": "youtube", "yutup": "youtube", "yu tub": "youtube",
        "gugıl": "google", "gogle": "google",
        "vatsap": "whatsapp", "watsapp": "whatsapp",
        "spotifay": "spotify",
        "instigram": "instagram", "istagram": "instagram",
        "hesapmakinesi": "hesap makinesi", "notdefteri": "not defteri",
        "görev yöneticis": "görev yöneticisi",
        "ekran görüntüs": "ekran görüntüsü",
        "ssal": "ss al", "krom": "chrome", "kırom": "chrome",
        "tarayıcı": "browser", "tarayici": "browser",
        "canlı": "live", "layv": "live",
        "sesiaç": "sesi aç", "sesikıs": "sesi kıs",
    }

    low = text.lower().strip()
    for source, target in replacements.items():
        low = re.sub(r"\b" + re.escape(source) + r"\b", target, low)

    command_phrases = [
        "youtube aç", "google aç", "whatsapp aç", "spotify aç", "instagram aç",
        "ekran görüntüsü al", "ss al", "saat kaç", "tarih", "görev yöneticisi",
        "not defteri", "hesap makinesi", "denetim masası", "cmd", "powershell",
        "sesi aç", "sesi kıs", "bilgisayarı kapat", "bilgisayarı yeniden başlat",
        "merhaba", "selam", "tavuk", "kevra", "neto",
    ]
    if len(low.split()) <= 4:
        close = difflib.get_close_matches(low, command_phrases, n=1, cutoff=0.72)
        if close:
            return close[0]
    return low


def _worker_clean_text(text: str) -> str:
    text = _worker_clean_word(text)
    if not text:
        return ""
    low = text.lower().strip()
    bad_exact = {"you", "i", "a", "the", "hı", "ıı", "eee", "aa", "ee", "hmm", "altyazı m.k.", "..."}
    if low in bad_exact:
        return ""
    bad_parts = ["altyazı", "abone ol", "kanalıma", "teşekkürler", "thank you", "subtitles", "izlediğiniz için", "video açıklamasında"]
    if any(part in low for part in bad_parts) and len(text) < 70:
        return ""
    known_single = {"tavuk", "kevra", "neto", "merhaba", "selam", "durdur", "başlat", "cmd", "powershell"}
    if len(low.split()) == 1 and low not in known_single and len(low) < 5:
        return ""
    return text


def probe_input_device(
    preferred_keywords: list[str],
    sd: Any | None = None,
) -> tuple[bool, Optional[int], str]:
    """Return whether an input device is available and which one would be used."""
    try:
        if sd is None:
            import sounddevice as sd_module
            sd = sd_module
    except Exception as exc:
        return False, None, f"Mikrofon altyapısı yüklenemedi: {exc}"

    try:
        devices = sd.query_devices()
    except Exception as exc:
        return False, None, f"Mikrofon listesi alınamadı: {exc}"

    input_devices: list[tuple[int, str]] = []
    for index, device in enumerate(devices):
        try:
            name = str(device.get("name", ""))
            channels = int(device.get("max_input_channels", 0))
            if channels > 0:
                input_devices.append((index, name))
        except Exception:
            pass

    if not input_devices:
        return False, None, "Hiç mikrofon bulunamadı."

    for keyword in preferred_keywords:
        keyword_low = str(keyword or "").lower().strip()
        if not keyword_low:
            continue
        for index, name in input_devices:
            if keyword_low in name.lower():
                return True, index, name

    try:
        default_input = sd.default.device[0]
        if default_input is not None and int(default_input) >= 0:
            index = int(default_input)
            if 0 <= index < len(devices):
                name = str(devices[index].get("name", "Varsayılan Mikrofon"))
                return True, index, name
    except Exception:
        pass

    index, name = input_devices[0]
    return True, index, name


def _worker_select_input_device(sd: Any, preferred_keywords: list[str]) -> tuple[Optional[int], str]:
    try:
        devices = sd.query_devices()
    except Exception as exc:
        _emit("status", text=f"Mikrofon listesi alınamadı: {exc}")
        return None, "Varsayılan Mikrofon"

    input_devices: list[tuple[int, str]] = []
    _emit("status", text="Mikrofonlar taranıyor...")
    for index, device in enumerate(devices):
        try:
            name = str(device.get("name", ""))
            channels = int(device.get("max_input_channels", 0))
            if channels > 0:
                input_devices.append((index, name))
                _emit("log", text=f"[MIC] {index}: {name}")
        except Exception:
            pass

    if not input_devices:
        _emit("mic", text="Mikrofon bulunamadı")
        raise RuntimeError("Hiç mikrofon bulunamadı.")

    for keyword in preferred_keywords:
        for index, name in input_devices:
            if keyword.lower() in name.lower():
                _emit("mic", text=name)
                _emit("status", text=f"Mikrofon seçildi: {name}")
                return index, name

    try:
        default_input = sd.default.device[0]
        if default_input is not None and int(default_input) >= 0:
            index = int(default_input)
            name = str(devices[index].get("name", "Varsayılan Mikrofon"))
            _emit("mic", text=name)
            _emit("status", text=f"Varsayılan mikrofon seçildi: {name}")
            return index, name
    except Exception:
        pass

    index, name = input_devices[0]
    _emit("mic", text=name)
    _emit("status", text=f"İlk mikrofon seçildi: {name}")
    return index, name


def _worker_wait_parent_command(command_path: str, offset: int) -> tuple[str, int]:
    """Wait after a transcript so the UI can answer/speak without feedback.

    Commands are read from a tiny append-only file. This remains available in
    consoleless PyInstaller builds and does not depend on stdio handles.
    """
    deadline = time.time() + 20.0
    while time.time() < deadline:
        try:
            with open(command_path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                line = handle.readline()
                if line:
                    offset = handle.tell()
                    try:
                        data = json.loads(line)
                        return str(data.get("command", "continue")), offset
                    except Exception:
                        return line.strip().lower() or "continue", offset
        except Exception:
            pass
        time.sleep(0.05)
    # Never leave the microphone worker permanently stuck if the UI missed a
    # continue signal. The parent can still terminate it on Stop.
    return "continue", offset


def _remote_audio_read_packets(path: str, offset: int) -> tuple[list[dict[str, Any]], int]:
    packets: list[dict[str, Any]] = []
    if not path:
        return packets, offset
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            while True:
                line = handle.readline()
                if not line:
                    break
                offset = handle.tell()
                try:
                    packet = json.loads(line)
                except Exception:
                    continue
                if isinstance(packet, dict):
                    packets.append(packet)
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return packets, offset


def _remote_audio_packet_bytes(packet: dict[str, Any]) -> bytes:
    chunk_b64 = str(
        packet.get("pcm16_b64")
        or packet.get("pcm16")
        or packet.get("audio")
        or ""
    ).strip()
    if not chunk_b64:
        return b""
    try:
        return base64.b64decode(chunk_b64.encode("ascii"), validate=True)
    except Exception:
        return b""


def live_worker_main(config_path: str) -> int:
    """Entry point for the isolated native speech process."""
    log_dir = _local_log_dir()
    crash_log = os.path.join(log_dir, "live_worker_crash.log")
    worker_log = os.path.join(log_dir, "live_worker.log")
    fault_handle = None

    try:
        fault_handle = open(crash_log, "a", encoding="utf-8", buffering=1)
        fault_handle.write(f"\n--- worker start {time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} ---\n")
        faulthandler.enable(fault_handle, all_threads=True)
    except Exception:
        fault_handle = None

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)

        global _WORKER_EVENT_PATH
        _WORKER_EVENT_PATH = str(config.get("event_path") or "") or None
        command_path = str(config.get("command_path") or "")
        command_offset = 0

        # Keep native runtimes conservative and predictable on Windows.
        os.environ.setdefault("OMP_NUM_THREADS", str(max(1, min(4, (os.cpu_count() or 4) // 2))))
        os.environ.setdefault("MKL_NUM_THREADS", os.environ["OMP_NUM_THREADS"])
        os.environ.setdefault("CT2_VERBOSE", "0")

        _emit("status", text="Live ses motoru ayrı süreçte hazırlanıyor...")

        import sounddevice as sd
        import numpy as np

        # Critical ordering: this worker never imports Tk/Qt. Loading torch first
        # avoids the Windows PyTorch-after-PyQt c10.dll collision.
        try:
            import torch  # noqa: F401
            _emit("log", text="Torch izole süreçte güvenli sırada yüklendi.")
        except Exception as exc:
            _emit("log", text=f"Torch ön yüklemesi kullanılamadı: {exc}")

        _emit("status", text="Whisper altyapısı yükleniyor...")
        from faster_whisper import WhisperModel

        model_size = str(config.get("model_size", "small"))
        _emit("status", text=f"Whisper yükleniyor: {model_size}")
        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(6, os.cpu_count() or 4)),
            num_workers=1,
        )
        _emit("status", text="Whisper hazır.")

        record_seconds = float(config.get("record_seconds", 5.5))
        sample_rate = int(config.get("sample_rate", 16000))
        silence_threshold = float(config.get("silence_threshold", 0.006))
        language = str(config.get("language", "tr"))
        tablet_audio_path = str(config.get("tablet_audio_path") or "").strip()
        last_text = ""
        ready_once = False
        remote_mode = bool(tablet_audio_path)
        remote_audio_offset = 0
        remote_audio_buffer = bytearray()
        remote_audio_last_packet = 0.0
        remote_audio_announced = False
        device_index: int | None = None
        device_name = "Tablet mikrofonu"
        if remote_mode:
            _emit("mic", text=device_name)
            _emit("status", text="Tablet mikrofon akışı bekleniyor...")
        else:
            preferred = list(config.get("preferred_keywords") or ["AudioRelay", "Audio Relay", "WO Mic", "Microphone", "Mikrofon"])
            device_index, device_name = _worker_select_input_device(sd, preferred)

        _emit("ready", text=device_name)

        while True:
            if not ready_once:
                _emit("status", text="Hazırlanıyor... 1 saniye sonra konuş")
                time.sleep(1.0)
                ready_once = True

            audio = None
            if remote_mode:
                frames = int(record_seconds * sample_rate)
                target_bytes = max(2, frames * 2)
                _emit("status", text=f"Dinliyor... ({device_name})")
                while len(remote_audio_buffer) < target_bytes:
                    packets, remote_audio_offset = _remote_audio_read_packets(tablet_audio_path, remote_audio_offset)
                    if packets:
                        for packet in packets:
                            event = str(packet.get("event") or "chunk").strip().lower()
                            if event == "start":
                                remote_audio_buffer.clear()
                                label = str(packet.get("label") or device_name or "Tablet mikrofonu").strip()
                                if label:
                                    device_name = label
                                if not remote_audio_announced:
                                    _emit("mic", text=device_name)
                                    remote_audio_announced = True
                                _emit("status", text=f"Dinliyor... ({device_name})")
                                continue
                            if event == "stop":
                                remote_audio_buffer.clear()
                                continue
                            chunk = _remote_audio_packet_bytes(packet)
                            if not chunk:
                                continue
                            if len(chunk) % 2 == 1:
                                chunk = chunk[:-1]
                            if not chunk:
                                continue
                            remote_audio_buffer.extend(chunk)
                            remote_audio_last_packet = time.time()
                            if not remote_audio_announced:
                                label = str(packet.get("label") or device_name or "Tablet mikrofonu").strip()
                                if label:
                                    device_name = label
                                _emit("mic", text=device_name)
                                remote_audio_announced = True
                    else:
                        if remote_audio_buffer and (time.time() - remote_audio_last_packet) > 0.6:
                            break
                        time.sleep(0.03)

                if not remote_audio_buffer:
                    time.sleep(0.05)
                    continue

                if len(remote_audio_buffer) >= target_bytes:
                    audio_bytes = bytes(remote_audio_buffer[:target_bytes])
                    del remote_audio_buffer[:target_bytes]
                else:
                    audio_bytes = bytes(remote_audio_buffer)
                    remote_audio_buffer.clear()

                if len(audio_bytes) % 2 == 1:
                    audio_bytes = audio_bytes[:-1]
                if len(audio_bytes) < 2:
                    continue

                audio_i16 = np.frombuffer(audio_bytes, dtype="<i2")
                if audio_i16.size == 0:
                    continue
                audio = (audio_i16.astype("float32") / 32768.0).reshape(-1, 1)
            else:
                _emit("status", text=f"Dinliyor... ({device_name})")
                frames = int(record_seconds * sample_rate)
                try:
                    audio = sd.rec(
                        frames,
                        samplerate=sample_rate,
                        channels=1,
                        dtype="float32",
                        device=device_index,
                    )
                    sd.wait()
                except Exception as exc:
                    _emit("status", text=f"Mikrofon kaydı alınamadı: {exc}")
                    time.sleep(1.0)
                    continue

                if audio is None:
                    _emit("status", text="Mikrofondan ses verisi alınamadı.")
                    continue

            level = float(np.max(np.abs(audio)))
            _emit("status", text=f"Ses seviyesi: {level:.4f}")
            if level < silence_threshold:
                _emit("status", text="Ses düşük, tekrar dinliyorum...")
                continue

            try:
                peak = max(level, 0.0001)
                if peak < 0.20:
                    gain = min(6.0, 0.20 / peak)
                    audio = np.clip(audio * gain, -1.0, 1.0)
                audio_i16 = (audio * 32767).astype("int16")
                fd, wav_path = tempfile.mkstemp(prefix="neto_live_", suffix=".wav")
                os.close(fd)
                channels = int(audio_i16.shape[1]) if getattr(audio_i16, "ndim", 1) > 1 else 1
                with wave.open(wav_path, "wb") as wav_file:
                    wav_file.setnchannels(max(1, channels))
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_i16.tobytes())
            except Exception as exc:
                _emit("status", text=f"Ses hazırlanamadı: {exc}")
                continue

            try:
                _emit("status", text="Yazıya çeviriyorum...")
                segments, _info = model.transcribe(
                    wav_path,
                    language=language,
                    task="transcribe",
                    vad_filter=False,
                    beam_size=2,
                    best_of=2,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.15,
                    log_prob_threshold=-1.2,
                    compression_ratio_threshold=2.5,
                    initial_prompt=(
                        "Türkçe konuşma. Komutlar ve kelimeler: tavuk, NetOps Agent, NetOps, "
                        "YouTube aç, Google aç, WhatsApp aç, Spotify aç, Instagram aç, "
                        "ekran görüntüsü al, saat kaç, bilgisayarı kapat, görev yöneticisi, "
                        "not defteri, hesap makinesi, sesi aç, sesi kıs, durdur, başlat."
                    ),
                )
                raw_text = " ".join(segment.text.strip() for segment in segments).strip()
                cleaned = _worker_clean_text(raw_text)
            except Exception as exc:
                _emit("status", text=f"Whisper hata: {exc}")
                cleaned = ""
            finally:
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

            if not cleaned or cleaned.lower() == last_text:
                _emit("status", text="Anlamlı konuşma algılanmadı.")
                continue

            last_text = cleaned.lower()
            _emit("transcript", text=cleaned)
            command, command_offset = _worker_wait_parent_command(command_path, command_offset)
            if command == "stop":
                break

        _emit("status", text="Live durdu.")
        return 0

    except BaseException as exc:
        detail = f"{type(exc).__name__}: {exc}"
        _append_log(worker_log, detail)
        _append_log(worker_log, traceback.format_exc())
        try:
            _emit("fatal", text=detail, traceback=traceback.format_exc())
        except Exception:
            pass
        return 2
    finally:
        try:
            if fault_handle:
                fault_handle.flush()
                fault_handle.close()
        except Exception:
            pass


def run_worker_from_argv(argv: Optional[list[str]] = None) -> int:
    args = list(argv or sys.argv)
    try:
        index = args.index("--neto-live-worker")
        config_path = args[index + 1]
    except Exception:
        print("NetOps Live worker config path missing.", file=sys.stderr, flush=True)
        return 64
    return live_worker_main(config_path)


class NetoLiveMode:
    def __init__(
        self,
        answer_func: Callable[[str], Any],
        speak_func: Optional[Callable[[str], Any]] = None,
        status_callback: Optional[Callable[[str], Any]] = None,
        transcript_callback: Optional[Callable[[str], Any]] = None,
        answer_callback: Optional[Callable[[str], Any]] = None,
        mic_callback: Optional[Callable[[str], Any]] = None,
        stopped_callback: Optional[Callable[[str], Any]] = None,
        preferred_keywords=("AudioRelay", "Audio Relay", "WO Mic", "Microphone", "Mikrofon"),
        model_size="base",
        language="tr",
        record_seconds=4.5,
        sample_rate=16000,
        silence_threshold=0.004,
        tts_enabled=True,
        tablet_audio_path: Optional[str] = None,
    ):
        self.answer_func = answer_func
        self.speak_func = speak_func
        self.status_callback = status_callback
        self.transcript_callback = transcript_callback
        self.answer_callback = answer_callback
        self.mic_callback = mic_callback
        self.stopped_callback = stopped_callback
        self.preferred_keywords = tuple(preferred_keywords)
        self.model_size = model_size
        self.language = language
        self.record_seconds = float(record_seconds)
        self.sample_rate = int(sample_rate)
        self.silence_threshold = float(silence_threshold)
        self.tts_enabled = bool(tts_enabled)
        self.tablet_audio_path = str(tablet_audio_path or "").strip()

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.process: Optional[subprocess.Popen[str]] = None
        self._intentional_stop = False
        self._lock = threading.RLock()
        self._config_path: Optional[str] = None
        self._event_path: Optional[str] = None
        self._command_path: Optional[str] = None
        self._event_offset = 0
        self._last_fatal = ""
        self.log_dir = _local_log_dir()
        self.stderr_log = os.path.join(self.log_dir, "live_worker_stderr.log")
        self.session_log = os.path.join(self.log_dir, "live_session.log")

    def _callback(self, callback: Optional[Callable[..., Any]], *args: Any) -> None:
        if callback:
            try:
                callback(*args)
            except Exception:
                pass

    def _status(self, text: str) -> None:
        try:
            print(f"[LIVE] {text}", flush=True)
        except Exception:
            pass
        _append_log(self.session_log, f"[{time.strftime('%H:%M:%S')}] {text}")
        self._callback(self.status_callback, str(text))

    def _build_command(self, config_path: str) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--neto-live-worker", config_path]
        return [sys.executable, os.path.abspath(__file__), "--neto-live-worker", config_path]

    def _write_config(self) -> str:
        fd, path = tempfile.mkstemp(prefix="neto_live_config_", suffix=".json")
        os.close(fd)
        event_fd, self._event_path = tempfile.mkstemp(prefix="neto_live_events_", suffix=".jsonl")
        command_fd, self._command_path = tempfile.mkstemp(prefix="neto_live_commands_", suffix=".jsonl")
        os.close(event_fd)
        os.close(command_fd)
        self._event_offset = 0
        config = {
            "preferred_keywords": list(self.preferred_keywords),
            "model_size": self.model_size,
            "language": self.language,
            "record_seconds": self.record_seconds,
            "sample_rate": self.sample_rate,
            "silence_threshold": self.silence_threshold,
            "event_path": self._event_path,
            "command_path": self._command_path,
            "tablet_audio_path": self.tablet_audio_path,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        return path

    def _popen_kwargs(self, stderr_handle: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": stderr_handle,
            "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return kwargs

    def _read_new_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        path = self._event_path
        if not path:
            return events
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self._event_offset)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    self._event_offset = handle.tell()
                    try:
                        events.append(json.loads(line))
                    except Exception as exc:
                        _append_log(self.stderr_log, f"Protocol error: {exc} | {line.rstrip()}")
        except Exception:
            pass
        return events

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                self._status("Live zaten açık.")
                return False
            self.running = True
            self._intentional_stop = False
            self._last_fatal = ""
            self.thread = threading.Thread(target=self._supervisor_loop, name="NetoLiveSupervisor", daemon=True)
            self.thread.start()
        self._status("Live güvenli yardımcı süreçte başlatılıyor...")
        return True

    def stop(self) -> bool:
        with self._lock:
            self._intentional_stop = True
            self.running = False
            process = self.process
        self._send_command("stop")

        if process and process.poll() is None:
            def terminate_later() -> None:
                try:
                    process.wait(timeout=1.5)
                except Exception:
                    try:
                        process.terminate()
                        process.wait(timeout=1.0)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
            threading.Thread(target=terminate_later, daemon=True).start()

        self._status("Live kapatıldı.")
        return True

    def is_running(self) -> bool:
        with self._lock:
            process = self.process
            if process is not None and process.poll() is not None:
                return False
            return bool(self.running)

    def _send_command(self, command: str) -> None:
        path = self._command_path
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8", buffering=1) as handle:
                handle.write(json.dumps({"command": command}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _handle_event(self, data: dict[str, Any]) -> None:
        event = str(data.get("event", ""))
        text = str(data.get("text", ""))

        if event == "status":
            self._status(text)
        elif event == "mic":
            self._callback(self.mic_callback, text)
        elif event == "log":
            _append_log(self.session_log, text)
        elif event == "ready":
            self._status("Live hazır, konuşabilirsin.")
        elif event == "fatal":
            self._last_fatal = text
            tb = str(data.get("traceback", ""))
            if tb:
                _append_log(self.stderr_log, tb)
            self._status(f"Live motoru başlatılamadı: {text}")
        elif event == "transcript":
            self._callback(self.transcript_callback, text)
            self._status("Komut/NetOps Agent işleniyor...")
            try:
                answer = self.answer_func(text)
            except Exception as exc:
                answer = f"NetOps Agent hata verdi: {exc}"
            if not answer:
                answer = "Cevap alınamadı."
            answer_text = str(answer)
            self._callback(self.answer_callback, answer_text)

            if self.tts_enabled and self.speak_func:
                try:
                    self.speak_func(answer_text)
                    time.sleep(min(8.0, max(2.0, len(answer_text) / 40.0)))
                except Exception as exc:
                    self._status(f"Sesli okuma hatası: {exc}")
            self._send_command("continue" if self.running else "stop")

    def _supervisor_loop(self) -> None:
        process: Optional[subprocess.Popen[Any]] = None
        exit_code: Optional[int] = None
        stderr_handle = None
        try:
            self._config_path = self._write_config()
            command = self._build_command(self._config_path)
            _append_log(self.session_log, "COMMAND: " + repr(command))
            stderr_handle = open(self.stderr_log, "a", encoding="utf-8", buffering=1)
            process = subprocess.Popen(command, **self._popen_kwargs(stderr_handle))
            with self._lock:
                self.process = process

            # Poll the event file. File IPC survives --windowed builds where
            # standard streams are intentionally missing.
            while True:
                for data in self._read_new_events():
                    self._handle_event(data)
                polled = process.poll()
                if polled is not None:
                    exit_code = polled
                    # Read events flushed immediately before process exit.
                    for _ in range(3):
                        time.sleep(0.03)
                        for data in self._read_new_events():
                            self._handle_event(data)
                    break
                time.sleep(0.05)
        except Exception as exc:
            self._last_fatal = f"{type(exc).__name__}: {exc}"
            _append_log(self.stderr_log, traceback.format_exc())
            self._status(f"Live yardımcı süreç hatası: {self._last_fatal}")
        finally:
            try:
                if stderr_handle:
                    stderr_handle.flush()
                    stderr_handle.close()
            except Exception:
                pass

            with self._lock:
                intentional = self._intentional_stop
                self.running = False
                self.process = None

            for temp_path in (self._config_path, self._event_path, self._command_path):
                if temp_path:
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            self._config_path = None
            self._event_path = None
            self._command_path = None

            if not intentional:
                if self._last_fatal:
                    reason = self._last_fatal
                elif exit_code not in (0, None):
                    reason = f"Yardımcı süreç beklenmedik biçimde kapandı (çıkış kodu {exit_code})."
                else:
                    reason = "Live ses motoru beklenmedik biçimde durdu."
                self._status(f"{reason} Neto açık kaldı. Log: {self.log_dir}")
                self._callback(self.stopped_callback, reason)
            else:
                self._status("Live durdu.")


if __name__ == "__main__" and "--neto-live-worker" in sys.argv:
    raise SystemExit(run_worker_from_argv(sys.argv))
