from config import SURFACE_PALETS
from neto_astryx_design import (
    ASTRYX_DARK,
    ASTRYX_LIGHT,
    ASTRYX_RADII,
    astryx_card_style,
    astryx_control_style,
    astryx_input_style,
    astryx_palette,
)


def test_astryx_palettes_expose_operational_surface_roles() -> None:
    required = {
        "bg",
        "sidebar",
        "card",
        "card_elevated",
        "accent",
        "accent_hover",
        "accent_text",
        "text_main",
        "text_dim",
        "entry_bg",
        "entry_border",
        "button_fg",
        "button_hover",
        "divider",
        "focus_ring",
    }

    assert required.issubset(ASTRYX_DARK)
    assert required.issubset(ASTRYX_LIGHT)
    assert ASTRYX_DARK["bg"] != ASTRYX_DARK["card"]
    assert ASTRYX_LIGHT["text_main"] != ASTRYX_LIGHT["text_dim"]


def test_astryx_styles_keep_geometry_stable() -> None:
    palette = astryx_palette("dark")

    control = astryx_control_style(palette)
    card = astryx_card_style(palette)
    entry = astryx_input_style(palette)

    assert control["corner_radius"] == ASTRYX_RADII["control"]
    assert card["corner_radius"] == ASTRYX_RADII["card"]
    assert entry["corner_radius"] == ASTRYX_RADII["control"]
    assert control["border_width"] == card["border_width"] == entry["border_width"] == 1


def test_existing_fluent_surface_alias_uses_astryx_tokens() -> None:
    assert SURFACE_PALETS["fluent"]["dark"]["accent"] == ASTRYX_DARK["accent"]
    assert SURFACE_PALETS["fluent"]["light"]["accent"] == ASTRYX_LIGHT["accent"]
