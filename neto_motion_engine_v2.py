from __future__ import annotations

import math
import threading
import time
import weakref

try:
    import pytweening as _pytweening
except Exception:
    _pytweening = None
from typing import Any, Callable, Optional

try:
    from neto_visual_driver import frame_ms as _visual_driver_frame_ms
except Exception as _visual_driver_error:
    _visual_driver_frame_ms = None
else:
    _visual_driver_error = None

BUILD = "23.0-animation-performance-modes"
DEFAULT_FRAME_MS = 14


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def linear(t: float) -> float:
    return _clamp(t)


def ease_out_cubic(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeOutCubic(t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_quart(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeOutQuart(t))
    return 1.0 - (1.0 - t) ** 4


def ease_in_out_cubic(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeInOutCubic(t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def smootherstep(t: float) -> float:
    t = _clamp(t)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def ease_out_quint(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeOutQuint(t))
    return 1.0 - (1.0 - t) ** 5


def ease_out_expo(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeOutExpo(t))
    if t >= 1.0:
        return 1.0
    return 1.0 - 2.0 ** (-8.0 * t)


def ease_out_back(t: float) -> float:
    t = _clamp(t)
    if _pytweening is not None:
        return float(_pytweening.easeOutBack(t))
    c1 = 0.86
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


def fluid_out(t: float) -> float:
    t = _clamp(t)
    expo = ease_out_expo(t)
    smooth = smootherstep(t)
    return _clamp((expo * 0.72) + (smooth * 0.28))


def spring_soft(t: float) -> float:
    t = _clamp(t)
    if t >= 1.0:
        return 1.0
    return _clamp(1.0 - math.exp(-8.0 * t) * math.cos(8.5 * t), 0.0, 1.035)


EASINGS = {
    "linear": linear,
    "ease_out_cubic": ease_out_cubic,
    "ease_out_quart": ease_out_quart,
    "ease_in_out_cubic": ease_in_out_cubic,
    "smootherstep": smootherstep,
    "ease_out_quint": ease_out_quint,
    "ease_out_expo": ease_out_expo,
    "ease_out_back": ease_out_back,
    "fluid_out": fluid_out,
    "spring_soft": spring_soft,
}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    if len(raw) != 6:
        raise ValueError(value)
    return (
        int(raw[0:2], 16),
        int(raw[2:4], 16),
        int(raw[4:6], 16),
    )


def _rgb_to_hex(value: tuple[float, float, float]) -> str:
    channels = [max(0, min(255, round(channel))) for channel in value]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def interpolate_color(start: str, end: str, progress: float) -> str:
    start_rgb = _hex_to_rgb(start)
    end_rgb = _hex_to_rgb(end)
    progress = _clamp(progress)
    return _rgb_to_hex((
        start_rgb[0] + (end_rgb[0] - start_rgb[0]) * progress,
        start_rgb[1] + (end_rgb[1] - start_rgb[1]) * progress,
        start_rgb[2] + (end_rgb[2] - start_rgb[2]) * progress,
    ))


def _runtime_preferences() -> dict:
    try:
        from neto_runtime_policy_v2 import motion_preferences
        value = motion_preferences()
        return value if isinstance(value, dict) else {}
    except Exception:
        return {"mode": "normal", "enabled": True, "duration_scale": 1.0, "frame_ms": DEFAULT_FRAME_MS}


class MotionEngine:
    """One Tk clock; replacement transitions always supersede old callbacks."""

    def __init__(self, root):
        if _visual_driver_frame_ms is None:
            raise RuntimeError(f"NetOps Visual Driver yüklenemedi: {_visual_driver_error}")
        self.root = root
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._timer = None
        self._in_tick = False
        self.errors = []

    def _alive(self):
        try:
            return bool(self.root is not None and self.root.winfo_exists())
        except Exception:
            return False

    def cancel(self, key):
        self._jobs.pop(str(key), None)
        if not self._jobs and self._timer is not None:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None

    def cancel_prefix(self, prefix):
        for key in list(self._jobs):
            if key.startswith(str(prefix)):
                self.cancel(key)

    def _schedule(self):
        if self._timer is None and self._jobs and not self._in_tick:
            self._timer = self.root.after(
                max(16, min(item["frame_ms"] for item in self._jobs.values())), self._tick
            )

    def _tick(self):
        self._timer = None
        if not self._alive():
            self._jobs.clear()
            return
        self._in_tick = True
        now = time.perf_counter()
        try:
            for key, state in list(self._jobs.items()):
                if self._jobs.get(key) is not state or now < state["started"]:
                    continue
                raw = _clamp((now - state["started"]) / state["duration"])
                try:
                    state["update"](1.0 if raw >= 1.0 else state["easing"](raw))
                except Exception as exc:
                    self.errors.append((key, str(exc)))
                    self.errors[:] = self.errors[-20:]
                    if self._jobs.get(key) is state:
                        self._jobs.pop(key, None)
                    continue
                # An update can replace its own key. Never finish the old job.
                if raw >= 1.0 and self._jobs.get(key) is state:
                    self._jobs.pop(key, None)
                    if callable(state["complete"]):
                        try:
                            state["complete"]()
                        except Exception as exc:
                            self.errors.append((key, str(exc)))
                            self.errors[:] = self.errors[-20:]
        finally:
            self._in_tick = False
            self._schedule()

    def tween(self, key, duration_ms, update, *, easing="ease_out_cubic",
              on_complete=None, delay_ms=0, force=False):
        key = str(key)
        self.cancel(key)
        if not self._alive():
            return key
        prefs = _runtime_preferences()
        scale = float(prefs.get("duration_scale", 1.0))
        if not prefs.get("enabled", True) or scale <= 0 or duration_ms <= 0:
            update(1.0)
            if callable(on_complete):
                on_complete()
            return key
        if prefs.get("mode") == "reduced":
            easing = "ease_out_cubic"
            frame_ms = max(32, int(_visual_driver_frame_ms(prefs.get("frame_ms", 32) or 32)))
        else:
            frame_ms = max(16, int(_visual_driver_frame_ms(prefs.get("frame_ms", 16) or 16)))
        easing_fn = EASINGS.get(easing, ease_out_cubic) if isinstance(easing, str) else easing
        self._jobs[key] = {
            "started": time.perf_counter() + max(0, delay_ms * scale) / 1000.0,
            "duration": max(0.055, duration_ms * scale / 1000.0),
            "frame_ms": frame_ms,
            "update": update, "easing": easing_fn, "complete": on_complete,
        }
        self._schedule()
        return key

    def number(self, key: str, start: float, end: float, setter: Callable[[float], None], *, duration_ms: int = 220, easing: str = "ease_out_quint", on_complete: Optional[Callable[[], None]] = None) -> str:
        start, end = float(start), float(end)
        last = {"value": None}

        def update(progress: float) -> None:
            value = start + (end - start) * progress
            previous = last["value"]
            if previous is not None and abs(float(previous) - value) < 0.01 and progress < 1.0:
                return
            last["value"] = value
            setter(value)

        return self.tween(key, duration_ms, update, easing=easing, on_complete=on_complete)

    def color(self, key: str, widget, option: str, start: str, end: str, *, duration_ms: int = 170, easing: str = "ease_out_cubic") -> str:
        last = {"value": None}

        def update(progress: float) -> None:
            try:
                if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                    self.cancel(key)
                    return
                value = interpolate_color(start, end, progress)
                if value == last["value"]:
                    return
                last["value"] = value
                widget.configure(**{option: value})
            except Exception:
                self.cancel(key)
        return self.tween(key, duration_ms, update, easing=easing)

    def fade_toplevel(self, window, *, start: float = 0.0, end: float = 1.0, duration_ms: int = 180, on_complete: Optional[Callable[[], None]] = None) -> str:
        key = f"fade:{id(window)}"
        try:
            window.attributes("-alpha", float(start))
        except Exception:
            if callable(on_complete):
                on_complete()
            return key
        return self.number(key, start, end, lambda value: window.attributes("-alpha", _clamp(value)), duration_ms=duration_ms, easing="fluid_out", on_complete=on_complete)

    def canvas_reveal(self, scrollable, *, offset: float = 0.032, duration_ms: int = 235) -> str:
        canvas = getattr(scrollable, "_parent_canvas", None)
        key = f"canvas:{id(scrollable)}"
        if canvas is None:
            return key
        try:
            canvas.yview_moveto(offset)
        except Exception:
            return key
        return self.tween(key, duration_ms, lambda progress: canvas.yview_moveto(max(0.0, offset * (1.0 - progress))), easing="fluid_out")

    def text(self, label, value: str, *, key: Optional[str] = None, min_duration_ms: int = 120, max_duration_ms: int = 850, on_complete: Optional[Callable[[], None]] = None) -> str:
        text = str(value or "")
        key = key or f"text:{id(label)}"
        if not text:
            try:
                label.configure(text="")
            except Exception:
                pass
            return key
        duration = max(min_duration_ms, min(max_duration_ms, 80 + len(text) * 7))
        shown = {"count": -1}
        def update(progress: float) -> None:
            count = len(text) if progress >= 1.0 else max(1, int(len(text) * progress))
            if count == shown["count"]:
                return
            shown["count"] = count
            try:
                label.configure(text=text[:count])
            except Exception:
                pass
        return self.tween(key, duration, update, easing="ease_out_quart", on_complete=on_complete)

    def progress_bar(self, bar, *, start: float = 0.0, end: float = 1.0, duration_ms: int = 650, key: Optional[str] = None) -> str:
        key = key or f"progress:{id(bar)}"
        try:
            bar.set(start)
        except Exception:
            pass
        last = {"value": None}

        def set_value(value: float) -> None:
            if hasattr(bar, "winfo_exists"):
                try:
                    if not bar.winfo_exists():
                        self.cancel(key)
                        return
                except Exception:
                    self.cancel(key)
                    return
            value = round(_clamp(value), 4)
            if value == last["value"]:
                return
            last["value"] = value
            bar.set(value)

        return self.number(key, start, end, set_value, duration_ms=duration_ms, easing="smootherstep")


_ENGINES: dict[int, tuple[Callable[[], Any], MotionEngine]] = {}
_ENGINE_LOCK = threading.RLock()


def get_motion_engine(root) -> MotionEngine:
    key = id(root)
    with _ENGINE_LOCK:
        current = _ENGINES.get(key)
        if current is not None:
            ref, engine = current
            if ref() is root:
                return engine
        engine = MotionEngine(root)
        try:
            ref = weakref.ref(root, lambda _ref, item=key: _ENGINES.pop(item, None))
        except TypeError:
            ref = lambda: root
        _ENGINES[key] = (ref, engine)
        return engine


def animate_text(root, label, text: str, **kwargs) -> str:
    return get_motion_engine(root).text(label, text, **kwargs)


