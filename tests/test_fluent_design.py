from config import SURFACE_PALETS, VALID_SURFACE_STYLES
from neto_settings_page import _normalize_surface_style
from temalar import _arayuz_stili_normalize
from neto_fluent_design import (
    FLUENT_CONTROL_HEIGHT,
    FLUENT_NAV_WIDTH,
    FLUENT_RADII,
    fluent_card_style,
    fluent_control_style,
    fluent_input_style,
)


def test_fluent_is_the_canonical_surface_style() -> None:
    assert "fluent" in VALID_SURFACE_STYLES
    assert _arayuz_stili_normalize("Fluent Design") == "fluent"
    assert _normalize_surface_style("Fluent Design") == "fluent"


def test_fluent_palettes_have_separate_readable_surfaces() -> None:
    dark = SURFACE_PALETS["fluent"]["dark"]
    light = SURFACE_PALETS["fluent"]["light"]

    for palette in (dark, light):
        assert {"bg", "sidebar", "card", "entry_bg", "entry_border", "neon", "text_main", "text_dim"}.issubset(palette)
        assert palette["bg"] != palette["card"]
        assert palette["text_main"] != palette["text_dim"]


def test_fluent_navigation_and_controls_use_compact_fixed_geometry() -> None:
    assert FLUENT_NAV_WIDTH == 304
    assert FLUENT_CONTROL_HEIGHT == 36
    assert FLUENT_RADII["control"] == 6


def test_fluent_surface_styles_keep_geometry_stable_across_windows() -> None:
    palette = SURFACE_PALETS["fluent"]["dark"]
    control = fluent_control_style(palette)
    card = fluent_card_style(palette)
    entry = fluent_input_style(palette)

    assert control["corner_radius"] == FLUENT_RADII["control"]
    assert control["border_width"] == 1
    assert card["corner_radius"] == FLUENT_RADII["card"]
    assert card["border_width"] == 1
    assert entry["corner_radius"] == FLUENT_RADII["control"]
    assert entry["border_width"] == 1
    assert control["fg_color"] == palette["button_fg"]
    assert entry["fg_color"] == palette["entry_bg"]
