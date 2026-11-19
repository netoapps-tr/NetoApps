"""NetOps Fluent Design tokens.

The tokens keep the existing CustomTkinter architecture intact while giving
every surface one predictable Windows-style visual language.
"""

from __future__ import annotations

from typing import Any

from neto_astryx_design import ASTRYX_DARK, ASTRYX_LIGHT

# Keep the public Fluent names for compatibility with saved settings and
# existing imports, while using the Astryx-inspired tokens as the current look.
FLUENT_DARK = dict(ASTRYX_DARK)
FLUENT_DARK["neon"] = FLUENT_DARK["accent"]
FLUENT_LIGHT = dict(ASTRYX_LIGHT)
FLUENT_LIGHT["neon"] = FLUENT_LIGHT["accent"]


FLUENT_PALETS = {"dark": FLUENT_DARK, "light": FLUENT_LIGHT}

FLUENT_RADII = {
    "window": 10,
    "card": 8,
    "control": 6,
    "compact_control": 4,
}

FLUENT_NAV_WIDTH = 304
FLUENT_CONTROL_HEIGHT = 36


def fluent_palette(mode: str = "dark") -> dict[str, Any]:
    """Return a copy so theme refreshes cannot mutate shared tokens."""
    return dict(FLUENT_PALETS.get(str(mode).lower(), FLUENT_DARK))


def _style_palette(palette: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a caller palette without mutating the shared Fluent tokens."""
    value = dict(FLUENT_DARK)
    if palette:
        value.update(palette)
    return value


def fluent_control_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the stable button style shared by every NetOps surface."""
    p = _style_palette(palette)
    return {
        "fg_color": p["button_fg"],
        "hover_color": p["button_hover"],
        "text_color": p["button_text"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": FLUENT_RADII["control"],
    }


def fluent_card_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the stable elevated card style used by dialogs and panels."""
    p = _style_palette(palette)
    return {
        "fg_color": p["card"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": FLUENT_RADII["card"],
    }


def fluent_input_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the stable input style used by entries and text boxes."""
    p = _style_palette(palette)
    return {
        "fg_color": p["entry_bg"],
        "text_color": p["text_main"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": FLUENT_RADII["control"],
    }


__all__ = [
    "FLUENT_DARK",
    "FLUENT_LIGHT",
    "FLUENT_PALETS",
    "FLUENT_RADII",
    "FLUENT_NAV_WIDTH",
    "FLUENT_CONTROL_HEIGHT",
    "fluent_palette",
    "fluent_control_style",
    "fluent_card_style",
    "fluent_input_style",
]
