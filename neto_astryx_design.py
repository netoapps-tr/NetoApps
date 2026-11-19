"""Astryx-inspired visual tokens for the native NetOps desktop.

This module intentionally stays dependency-free. Astryx is React/StyleX based,
while NetOps remains a CustomTkinter application, so only the visual language
is adapted here.
"""

from __future__ import annotations

from typing import Any


ASTRYX_DARK: dict[str, str] = {
    "design_language": "astryx",
    "bg": "#0B0E13",
    "sidebar": "#11151D",
    "card": "#171C25",
    "card_elevated": "#1E2632",
    "accent": "#2F7CF6",
    "accent_hover": "#4A8DFF",
    "accent_text": "#F7FAFF",
    "text_main": "#F2F5FA",
    "text_dim": "#9AA6B8",
    "entry_bg": "#11161F",
    "entry_border": "#354154",
    "button_fg": "#161D28",
    "button_hover": "#222B39",
    "button_text": "#F2F5FA",
    "divider": "#293342",
    "focus_ring": "#2F7CF6",
    "status_good": "#41D6A2",
    "status_warn": "#F4B860",
}

ASTRYX_LIGHT: dict[str, str] = {
    "design_language": "astryx",
    "bg": "#F4F6F9",
    "sidebar": "#FFFFFF",
    "card": "#FFFFFF",
    "card_elevated": "#FFFFFF",
    "accent": "#1F6FEB",
    "accent_hover": "#1859BF",
    "accent_text": "#FFFFFF",
    "text_main": "#182230",
    "text_dim": "#5F6B7A",
    "entry_bg": "#FFFFFF",
    "entry_border": "#CDD5E0",
    "button_fg": "#F8FAFC",
    "button_hover": "#E9EEF5",
    "button_text": "#182230",
    "divider": "#DCE3EC",
    "focus_ring": "#1F6FEB",
    "status_good": "#168C68",
    "status_warn": "#B66B00",
}

ASTRYX_RADII = {
    "window": 14,
    "card": 12,
    "control": 8,
    "compact_control": 6,
}

ASTRYX_PALETTES = {"dark": ASTRYX_DARK, "light": ASTRYX_LIGHT}


def astryx_palette(mode: str = "dark") -> dict[str, Any]:
    """Return a copy so runtime theme refreshes cannot mutate shared tokens."""
    return dict(ASTRYX_PALETTES.get(str(mode).lower(), ASTRYX_DARK))


def astryx_control_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    p = astryx_palette("dark")
    if palette:
        p.update(palette)
    return {
        "fg_color": p["button_fg"],
        "hover_color": p["button_hover"],
        "text_color": p["button_text"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": ASTRYX_RADII["control"],
    }


def astryx_card_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    p = astryx_palette("dark")
    if palette:
        p.update(palette)
    return {
        "fg_color": p["card"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": ASTRYX_RADII["card"],
    }


def astryx_input_style(palette: dict[str, Any] | None = None) -> dict[str, Any]:
    p = astryx_palette("dark")
    if palette:
        p.update(palette)
    return {
        "fg_color": p["entry_bg"],
        "text_color": p["text_main"],
        "border_color": p["entry_border"],
        "border_width": 1,
        "corner_radius": ASTRYX_RADII["control"],
    }


__all__ = [
    "ASTRYX_DARK",
    "ASTRYX_LIGHT",
    "ASTRYX_RADII",
    "ASTRYX_PALETTES",
    "astryx_palette",
    "astryx_control_style",
    "astryx_card_style",
    "astryx_input_style",
]
