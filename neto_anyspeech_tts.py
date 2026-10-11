from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from piper.download_voices import download_voice
    from piper.voice import PiperVoice

    K_PIPER = True
except Exception:
    download_voice = None  # type: ignore[assignment]
    PiperVoice = None  # type: ignore[assignment]
    K_PIPER = False

try:
    import pygame

    K_PYGAME = True
except Exception:
    pygame = None
    K_PYGAME = False

try:
    import winsound

    K_WINSOUND = True
except Exception:
    winsound = None
    K_WINSOUND = False

PIPER_DEFAULT_VOICE = os.getenv("NETO_TTS_VOICE", "tr_TR-dfki-medium")
PIPER_VOICE_DIR = Path(
    os.getenv("NETO_TTS_VOICE_DIR")
    or (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "NetoAsistan"
        / "piper_voices"
    )
)
PIPER_MAX_CHARS = 900
PIPER_GAP_SECONDS = 0.04

_VOICE_CODE_RE = re.compile(r"^[A-Za-z]{2}_[A-Za-z]{2}-[^-]+-[A-Za-z0-9_]+$")
_SPEAK_LOCK = threading.Lock()
_VOICE_LOCK = threading.Lock()
_WARNING_LOCK = threading.Lock()
_WARNING_CALLBACK: Callable[[str], None] | None = None
_LAST_WARNING: dict[str, float | str] = {"text": "", "ts": 0.0}
_VOICE_STATE: dict[str, Any] = {
    "voice_code": "",
    "voice": None,
    "model_path": None,
    "config_path": None,
}


def reset_voice_cache() -> None:
    with _VOICE_LOCK:
        _VOICE_STATE.update(
            {
                "voice_code": "",
                "voice": None,
                "model_path": None,
                "config_path": None,
            }
        )


def set_warning_callback(callback: Callable[[str], None] | None) -> None:
    global _WARNING_CALLBACK
    _WARNING_CALLBACK = callback


def _notify_warning(message: str) -> None:
    msg = _normalize_text(message)
    if not msg:
        return

    now = time.monotonic()
    with _WARNING_LOCK:
        last_text = str(_LAST_WARNING.get("text") or "")
        last_ts = float(_LAST_WARNING.get("ts") or 0.0)
        if msg == last_text and (now - last_ts) < 12.0:
            return
        _LAST_WARNING["text"] = msg
        _LAST_WARNING["ts"] = now

    callback = _WARNING_CALLBACK
    if callable(callback):
        try:
            callback(msg)
            return
        except Exception:
            pass

    try:
        print(f"[PiperTTS][WARN] {msg}", flush=True)
    except Exception:
        pass


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if callable(logger):
        try:
            logger(message)
        except Exception:
            pass


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _split_text(text: str, max_chars: int = PIPER_MAX_CHARS) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    sentence_buffer: list[str] = []
    current_len = 0

    sentences = re.findall(r"[^.!?…]+[.!?…]*", text) or [text]
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            if sentence_buffer:
                chunks.append(" ".join(sentence_buffer).strip())
                sentence_buffer = []
                current_len = 0

            words = sentence.split()
            word_buffer: list[str] = []
            word_len = 0
            for word in words:
                candidate_len = word_len + len(word) + (1 if word_buffer else 0)
                if word_buffer and candidate_len > max_chars:
                    chunks.append(" ".join(word_buffer).strip())
                    word_buffer = [word]
                    word_len = len(word)
                else:
                    word_buffer.append(word)
                    word_len = candidate_len
            if word_buffer:
                chunks.append(" ".join(word_buffer).strip())
            continue

        extra = len(sentence) + (1 if sentence_buffer else 0)
        if sentence_buffer and current_len + extra > max_chars:
            chunks.append(" ".join(sentence_buffer).strip())
            sentence_buffer = [sentence]
            current_len = len(sentence)
        else:
            sentence_buffer.append(sentence)
            current_len += extra

    if sentence_buffer:
        chunks.append(" ".join(sentence_buffer).strip())

    return [chunk for chunk in chunks if chunk]


def _safe_remove(path: str | os.PathLike[str] | None) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _play_file(path: str, logger: Callable[[str], None] | None = None) -> None:
    if not os.path.exists(path) or os.path.getsize(path) <= 0:
        raise FileNotFoundError(path)

    if K_PYGAME:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(0.92)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        return

    if K_WINSOUND and winsound is not None:
        winsound.PlaySound(path, winsound.SND_FILENAME)
        return

    raise RuntimeError("Ses oynatma motoru bulunamadi.")


def _is_piper_voice_code(candidate: str) -> bool:
    return bool(_VOICE_CODE_RE.match(candidate.strip()))


def _resolve_voice_code(voice_candidates: Iterable[str] | None) -> str:
    if isinstance(voice_candidates, str):
        candidate = _normalize_text(voice_candidates)
        if candidate and _is_piper_voice_code(candidate):
            return candidate

    for item in voice_candidates or ():
        candidate = _normalize_text(str(item))
        if candidate and _is_piper_voice_code(candidate):
            return candidate
    return PIPER_DEFAULT_VOICE


def _voice_paths(voice_code: str) -> tuple[Path, Path]:
    model_path = PIPER_VOICE_DIR / f"{voice_code}.onnx"
    config_path = PIPER_VOICE_DIR / f"{voice_code}.onnx.json"
    return model_path, config_path


def _ensure_voice_files(voice_code: str, logger: Callable[[str], None] | None = None) -> tuple[Path, Path]:
    model_path, config_path = _voice_paths(voice_code)
    if model_path.exists() and config_path.exists():
        return model_path, config_path

    if download_voice is None:
        raise RuntimeError("Piper ses modeli indirilemiyor. piper-tts kurulu degil.")

    PIPER_VOICE_DIR.mkdir(parents=True, exist_ok=True)
    _log(logger, f"[PiperTTS] Model indiriliyor: {voice_code}")
    download_voice(voice_code, PIPER_VOICE_DIR)

    if not model_path.exists() or not config_path.exists():
        raise RuntimeError(f"Piper modeli indirilemedi: {voice_code}")

    return model_path, config_path


def _load_voice(voice_code: str, logger: Callable[[str], None] | None = None) -> PiperVoice:
    if PiperVoice is None:
        raise RuntimeError("Piper ses motoru yuklenemedi.")

    with _VOICE_LOCK:
        cached_code = str(_VOICE_STATE.get("voice_code") or "")
        cached_voice = _VOICE_STATE.get("voice")
        if cached_code == voice_code and cached_voice is not None:
            return cached_voice  # type: ignore[return-value]

        model_path, config_path = _ensure_voice_files(voice_code, logger=logger)
        _log(logger, f"[PiperTTS] Model yukleniyor: {voice_code}")
        voice = PiperVoice.load(model_path, config_path)
        _VOICE_STATE.update(
            {
                "voice_code": voice_code,
                "voice": voice,
                "model_path": model_path,
                "config_path": config_path,
            }
        )
        return voice


def preload_voice(
    voice_candidates: Iterable[str] = (),
    *,
    logger: Callable[[str], None] | None = None,
) -> bool:
    """Load the Piper voice into memory ahead of the first spoken reply."""
    voice_code = _resolve_voice_code(voice_candidates)
    try:
        _load_voice(voice_code, logger=logger)
        return True
    except Exception as exc:
        _log(logger, f"[PiperTTS][PRELOAD] {exc}")
        return False


def _synthesize_to_wav(voice: PiperVoice, text: str, wav_path: str) -> None:
    with wave.open(wav_path, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)


def speak_text(
    text: str,
    *,
    voice_candidates: Iterable[str] = (),
    logger: Callable[[str], None] | None = None,
) -> bool:
    clean = _normalize_text(text)
    if not clean:
        return False

    chunks = _split_text(clean, PIPER_MAX_CHARS)
    if not chunks:
        return False

    voice_code = _resolve_voice_code(voice_candidates)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            voice = _load_voice(voice_code, logger=logger)
            with _SPEAK_LOCK:
                for index, chunk in enumerate(chunks):
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    wav_path = tmp.name
                    tmp.close()
                    try:
                        _synthesize_to_wav(voice, chunk, wav_path)
                        _play_file(wav_path, logger=logger)
                    finally:
                        _safe_remove(wav_path)

                    if index < len(chunks) - 1:
                        time.sleep(PIPER_GAP_SECONDS)
            return True
        except Exception as exc:
            last_exc = exc
            _log(logger, f"[PiperTTS] {exc}")
            if attempt == 0:
                reset_voice_cache()
                time.sleep(0.2)
                continue
            _notify_warning(str(exc))
            raise RuntimeError(f"Yerel TTS ses motoru baslatilamadi: {exc}") from exc

    if last_exc is not None:
        _notify_warning(str(last_exc))
        raise RuntimeError(f"Yerel TTS ses motoru baslatilamadi: {last_exc}") from last_exc
    return False
