"""NetOps-specific visual layer for CustomTkinter buttons.

The application has several panels that create buttons at different times. This
module keeps their visual language in one place so a late-created panel does not
fall back to the old flat CustomTkinter defaults.
"""

from __future__ import annotations

from typing import Any, Iterable

import customtkinter as ctk
from PIL import Image, ImageDraw


_DARK = {
    "surface": "#202633",
    "surface_hover": "#2B3548",
    "surface_border": "#39465E",
    "primary": "#4F7CFF",
    "primary_hover": "#6A92FF",
    "danger": "#A8324B",
    "danger_hover": "#C44863",
    "text": "#F3F6FF",
    "muted": "#B6C0D4",
}

_LIGHT = {
    "surface": "#F2F6FC",
    "surface_hover": "#E4ECF9",
    "surface_border": "#C9D6EC",
    "primary": "#3F68E8",
    "primary_hover": "#5C82F4",
    "danger": "#B6374C",
    "danger_hover": "#D15267",
    "text": "#172033",
    "muted": "#5F6D84",
}

_INPUT_ICON_CACHE: dict[tuple[str, int, str], ctk.CTkImage] = {}


def input_icon(kind: str, size: int = 16, color: str = "#DCE7FF") -> ctk.CTkImage:
    """Return a supersampled icon for the compact message bar."""
    key = (str(kind).lower(), int(size), str(color))
    cached = _INPUT_ICON_CACHE.get(key)
    if cached is not None:
        return cached

    size = max(12, int(size))
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    kind = str(kind).lower()

    def point(x: float, y: float) -> tuple[int, int]:
        return round(x * scale), round(y * scale)

    def rounded_line(points: list[tuple[float, float]], fill: str, width: float) -> None:
        scaled = [point(x, y) for x, y in points]
        line_width = max(1, round(width * scale))
        draw.line(scaled, fill=fill, width=line_width, joint="curve")
        radius = line_width / 2
        for x, y in (scaled[0], scaled[-1]):
            draw.ellipse(
                (round(x - radius), round(y - radius), round(x + radius), round(y + radius)),
                fill=fill,
            )

    if kind == "plus":
        center = size / 2
        rounded_line([(3, center), (size - 3, center)], color, 2.2)
        rounded_line([(center, 3), (center, size - 3)], color, 2.2)
    elif kind == "send":
        plane = [point(2, size / 2), point(size - 2, 2), point(size - 5, size - 2), point(size / 2, size * 0.64)]
        draw.polygon(plane, fill=color)
        rounded_line(
            [(2.8, size / 2), (size / 2, size * 0.64), (size - 5, size - 2)],
            "#08090D",
            1.0,
        )
    elif kind == "ai":
        # Clean NetOps chevron with a solid, readable silhouette.
        draw.polygon(
            [
                point(size / 2, 2),
                point(size - 2, size - 2),
                point(size - 6, size - 2),
                point(size / 2, size * 0.34),
                point(6, size - 2),
                point(2, size - 2),
            ],
            fill=color,
        )
    elif kind == "waveform":
        center = size / 2
        bars = (8, 14, 20, 14, 8)
        positions = (4, 7.5, 11, 14.5, 18)
        for x, bar_height in zip(positions, bars):
            half = bar_height / 2
            rounded_line([(x, center - half), (x, center + half)], color, 2.0)
    elif kind == "camera":
        line = 1.6
        draw.rounded_rectangle(
            (*point(1, 4), *point(size - 2, size - 2)),
            radius=round(size * scale / 5),
            outline=color,
            width=round(line * scale),
        )
        draw.rounded_rectangle(
            (*point(size / 3, 2), *point(size * 2 / 3, 5)),
            radius=round(scale),
            fill=color,
        )
        lens = max(3, size // 3)
        left = (size - lens) // 2
        top = (size - lens + 2) // 2
        draw.ellipse((*point(left, top), *point(left + lens, top + lens)), outline=color, width=round(line * scale))
        draw.ellipse(
            (*point(left + lens / 2 - 1, top + lens / 2 - 1),
             *point(left + lens / 2 + 1, top + lens / 2 + 1)),
            fill=color,
        )
    elif kind == "keyboard":
        line = 1.5
        draw.rounded_rectangle(
            (*point(1, 3), *point(size - 2, size - 3)),
            radius=round(2 * scale),
            outline=color,
            width=round(line * scale),
        )
        for row, count in ((0, 5), (1, 4)):
            y = 6 + row * max(3, size // 4)
            gap = max(2, size // (count + 2))
            for col in range(count):
                x = 3 + col * gap
                draw.rounded_rectangle((*point(x, y), *point(x + 1, y + 1)), radius=scale, fill=color)
        rounded_line([(size / 3, size - 5), (size * 2 / 3, size - 5)], color, line)
    else:
        center = size / 2
        body_w = max(3, size // 4)
        draw.rounded_rectangle(
            (*point(center - body_w, 1), *point(center + body_w, size - 6)),
            radius=body_w,
            outline=color,
            width=round(1.6 * scale),
        )
        draw.arc((*point(2, size / 4), *point(size - 3, size - 2)), 0, 180, fill=color, width=round(1.6 * scale))
        rounded_line([(center, size - 5), (center, size - 2)], color, 1.6)
        rounded_line([(center - 4, size - 1), (center + 4, size - 1)], color, 1.6)

    image = image.resize((size, size), Image.Resampling.LANCZOS)
    icon = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
    _INPUT_ICON_CACHE[key] = icon
    return icon


def _is_dark() -> bool:
    try:
        return str(ctk.get_appearance_mode()).lower() == "dark"
    except Exception:
        return True


def _palette() -> dict[str, str]:
    return dict(_DARK if _is_dark() else _LIGHT)


def _text_of(button: Any) -> str:
    try:
        return str(button.cget("text") or "").strip().lower()
    except Exception:
        return ""


def _variant(button: Any, primary: bool | None) -> str:
    if primary is True:
        return "primary"
    if primary is False:
        return "secondary"

    text = _text_of(button)
    if any(token in text for token in ("kapalı", "kapat", "sil", "durdur", "devre dışı")):
        return "danger"
    if any(
        token in text
        for token in (
            "gönder",
            "başlat",
            "başla",
            "aç",
            "kaydet",
            "uygula",
            "otomasyon merkezi",
            "web sohbeti",
            "android cihaz",
            "netops agent",
        )
    ):
        return "primary"
    return "secondary"


def apply_button(
    button: Any,
    *,
    primary: bool | None = None,
    compact: bool = False,
    palette: dict[str, Any] | None = None,
    force: bool = False,
) -> bool:
    """Apply the NetOps button language without changing layout geometry."""
    if not isinstance(button, ctk.CTkButton):
        return False
    if getattr(button, "_neto_modern_skip", False):
        return False
    if getattr(button, "_neto_modernized", False) and not force:
        return False

    colors = _palette()
    if palette and str(palette.get("tema", "")).lower() == "light":
        colors = dict(_LIGHT)

    variant = _variant(button, primary)
    if variant == "primary":
        fg_color = colors["primary"]
        hover_color = colors["primary_hover"]
        text_color = "#FFFFFF"
        border_color = colors["primary_hover"]
    elif variant == "danger":
        fg_color = colors["danger"]
        hover_color = colors["danger_hover"]
        text_color = "#FFFFFF"
        border_color = colors["danger_hover"]
    else:
        fg_color = colors["surface"]
        hover_color = colors["surface_hover"]
        text_color = colors["text"]
        border_color = colors["surface_border"]

    try:
        button.configure(
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=1,
            border_color=border_color,
            corner_radius=10 if compact else 12,
        )
        button._neto_modernized = True
        button._neto_modern_variant = variant
        return True
    except Exception:
        return False


def _walk(parent: Any) -> Iterable[Any]:
    try:
        children = list(parent.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk(child)


def apply_tree(
    parent: Any,
    palette: dict[str, Any] | None = None,
    *,
    primary_names: set[str] | None = None,
    force: bool = False,
) -> int:
    """Modernize every button below ``parent`` and return the count changed."""
    if parent is None:
        return 0
    primary_names = {str(name).strip().lower() for name in (primary_names or set())}
    changed = 0
    for widget in _walk(parent):
        if not isinstance(widget, ctk.CTkButton):
            continue
        text = _text_of(widget)
        forced = True if text in primary_names else None
        if apply_button(widget, primary=forced, palette=palette, force=force):
            changed += 1
    return changed


__all__ = ["apply_button", "apply_tree", "input_icon"]
