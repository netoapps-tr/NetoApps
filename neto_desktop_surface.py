"""Utility-first desktop surface for the NetOps CustomTkinter application.

The module owns only the visual home surface. The main application supplies
callbacks, state, and palette tokens, so existing NetOps services remain the
single source of truth.
"""

from __future__ import annotations

from typing import Any, Callable


_NAVIGATION = (
    ("overview", "Genel Bakış", "overview"),
    ("devices", "Cihazlar", "devices"),
    ("now_playing", "Now Playing", "music"),
    ("automations", "Otomasyonlar", "layers"),
    ("logs", "Günlükler", "logs"),
    ("settings", "Ayarlar", "settings"),
)


_CARDS = (
    ("devices", "Cihazlar", "Bağlı cihazlar ve Remote durumu", "devices"),
    ("automation", "Otomasyon", "Çalışan akışlar ve zamanlayıcılar", "layers"),
    ("media", "Now Playing", "Medya oturumu ve son parça", "music"),
    ("health", "Sistem Durumu", "CPU, RAM ve servis sağlığı", "system"),
)


def navigation_items() -> tuple[tuple[str, str, str], ...]:
    """Return the stable text navigation contract used by the desktop shell."""
    return _NAVIGATION


def dashboard_cards(locale: str = "tr") -> tuple[dict[str, str], ...]:
    """Return compact dashboard cards without creating any Tk widgets."""
    if str(locale).lower().startswith("en"):
        values = (
            ("devices", "Devices", "Connected devices and Remote status", "devices"),
            ("automation", "Automation", "Running flows and schedules", "layers"),
            ("media", "Now Playing", "Media session and current track", "music"),
            ("health", "System Status", "CPU, RAM, and service health", "system"),
        )
    else:
        values = _CARDS
    return tuple(
        {"key": key, "title": title, "detail": detail, "icon": icon}
        for key, title, detail, icon in values
    )


def dashboard_copy(locale: str = "tr") -> dict[str, str]:
    """Return non-conversational copy for the home dashboard."""
    if str(locale).lower().startswith("en"):
        return {
            "eyebrow": "NETOPS / CONTROL DESK",
            "title": "Overview",
            "subtitle": "Monitor your workstation and launch tools from one place.",
            "activity": "Activity",
            "ready": "Ready",
            "empty": "No recent activity.",
        }
    return {
        "eyebrow": "NETOPS / KONTROL MASASI",
        "title": "Genel Bakış",
        "subtitle": "Bilgisayarını izle ve araçlarını tek bir yerden aç.",
        "activity": "Son Etkinlik",
        "ready": "Hazır",
        "empty": "Henüz bir etkinlik yok.",
    }


def layout_contract() -> dict[str, int]:
    """Return geometry limits that keep the surface usable on smaller windows."""
    return {
        "min_width": 760,
        "sidebar_width": 238,
        "surface_padding": 24,
        "card_radius": 8,
        "control_height": 36,
    }


def _icon_for(icon_factory: Callable[[str, int], Any] | None, name: str) -> Any:
    if not callable(icon_factory):
        return None
    try:
        return icon_factory(name, 16)
    except Exception:
        return None


def build_native_dashboard(
    ctk: Any,
    parent: Any,
    palette: dict[str, Any],
    callbacks: dict[str, Callable[[], Any]] | None = None,
    icon_factory: Callable[[str, int], Any] | None = None,
) -> Any:
    """Build the compact home dashboard and return its root frame.

    ``callbacks`` is intentionally a plain mapping. It keeps the module
    independent from the large legacy main file and makes each button safe to
    omit when a service is unavailable.
    """
    callbacks = dict(callbacks or {})
    p = dict(palette or {})
    bg = p.get("bg", "#0B0E13")
    sidebar = p.get("sidebar", "#11151D")
    card = p.get("card", "#171C25")
    elevated = p.get("card_elevated", "#1E2632")
    border = p.get("entry_border", "#354154")
    accent = p.get("neon", p.get("accent", "#2F7CF6"))
    text = p.get("text_main", "#F2F5FA")
    dim = p.get("text_dim", "#9AA6B8")
    copy = dashboard_copy("tr")

    surface = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    surface.grid_columnconfigure(0, weight=1)
    surface.grid_rowconfigure(3, weight=1)

    header = ctk.CTkFrame(surface, fg_color="transparent", height=74)
    header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
    header.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        header,
        text=copy["eyebrow"],
        text_color=accent,
        font=("Segoe UI Semibold", 10),
        anchor="w",
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        header,
        text=copy["title"],
        text_color=text,
        font=("Segoe UI Semibold", 26),
        anchor="w",
    ).grid(row=1, column=0, sticky="w", pady=(2, 0))
    ctk.CTkLabel(
        header,
        text=copy["subtitle"],
        text_color=dim,
        font=("Segoe UI", 11),
        anchor="w",
    ).grid(row=2, column=0, sticky="w", pady=(2, 0))

    status = ctk.CTkFrame(
        header,
        fg_color=card,
        border_width=1,
        border_color=border,
        corner_radius=8,
        width=112,
        height=34,
    )
    status.grid(row=0, column=1, rowspan=3, sticky="e", padx=(16, 0))
    status.grid_propagate(False)
    ctk.CTkLabel(status, text="●", text_color=p.get("status_good", "#41D6A2"), font=("Segoe UI", 12)).pack(
        side="left", padx=(12, 5)
    )
    ctk.CTkLabel(status, text=copy["ready"], text_color=text, font=("Segoe UI Semibold", 10)).pack(
        side="left", padx=(0, 10)
    )

    divider = ctk.CTkFrame(surface, height=1, fg_color=border, corner_radius=0)
    divider.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))

    cards_frame = ctk.CTkFrame(surface, fg_color="transparent")
    cards_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
    for column in range(4):
        cards_frame.grid_columnconfigure(column, weight=1, uniform="dashboard-card")

    card_widgets: dict[str, Any] = {}
    for column, item in enumerate(dashboard_cards("tr")):
        widget = ctk.CTkFrame(
            cards_frame,
            fg_color=card,
            border_width=1,
            border_color=border,
            corner_radius=8,
            height=92,
        )
        widget.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 5 if column < 3 else 0))
        widget.grid_propagate(False)
        widget.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            widget,
            text=item["title"],
            text_color=text,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        ctk.CTkLabel(
            widget,
            text=item["detail"],
            text_color=dim,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        card_widgets[item["key"]] = widget
        command = callbacks.get(item["key"])
        if callable(command):
            widget.bind("<Button-1>", lambda _event, action=command: action())

    activity = ctk.CTkFrame(
        surface,
        fg_color=sidebar,
        border_width=1,
        border_color=border,
        corner_radius=8,
    )
    activity.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
    activity.grid_columnconfigure(0, weight=1)
    activity.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        activity,
        text=copy["activity"],
        text_color=text,
        font=("Segoe UI Semibold", 13),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
    activity_body = ctk.CTkScrollableFrame(
        activity,
        fg_color="transparent",
        corner_radius=0,
        border_width=0,
        scrollbar_button_color=card,
        scrollbar_button_hover_color=elevated,
    )
    activity_body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
    ctk.CTkLabel(
        activity_body,
        text=copy["empty"],
        text_color=dim,
        font=("Segoe UI", 11),
        anchor="w",
    ).pack(fill="x", padx=8, pady=8)

    surface._neto_dashboard_refs = {
        "status": status,
        "cards": card_widgets,
        "activity": activity_body,
    }
    return surface


__all__ = [
    "build_native_dashboard",
    "dashboard_cards",
    "dashboard_copy",
    "layout_contract",
    "navigation_items",
]
