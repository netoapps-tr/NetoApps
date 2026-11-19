"""Embedded Lucide-style icons for the native NetOps Qt interface.

The glyphs are based on the open-source Lucide icon style (ISC licensed)
and are rendered locally as SVG, so NetOps does not depend on Windows stock
icons, a web connection, or an additional icon package at runtime.
"""

from __future__ import annotations

from functools import lru_cache
from html import escape

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


ICON_SVG: dict[str, str] = {
    "message": '<path d="M21 15a4 4 0 0 1-4 4H7l-4 4V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>',
    "devices": '<rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>',
    "media": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "workflow": '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M21 13h-2a2 2 0 0 0-2 2v2a2 2 0 0 1-2 2h-2"/><path d="M21 3h-2a2 2 0 0 0-2 2v2a2 2 0 0 1-2 2H9"/><path d="M3 13v-2a2 2 0 0 1 2-2h2"/>',
    "remote": '<circle cx="12" cy="12" r="3"/><path d="M18.36 5.64a9 9 0 0 1 0 12.72"/><path d="M5.64 18.36a9 9 0 0 1 0-12.72"/><path d="M21.19 2.81a13 13 0 0 1 0 18.38"/><path d="M2.81 21.19a13 13 0 0 1 0-18.38"/>',
    "system": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "settings": '<path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.42 1.42-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V20h-2v-.08a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06-1.42-1.42.06-.06A1.7 1.7 0 0 0 9.4 15a1.7 1.7 0 0 0-1.56-1.03H7v-2h.84A1.7 1.7 0 0 0 9.4 11a1.7 1.7 0 0 0-.34-1.88L9 9.06l1.42-1.42.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 13.39 6.5V6h2v.5a1.7 1.7 0 0 0 1.03 1.54 1.7 1.7 0 0 0 1.88-.34l.06-.06 1.42 1.42-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.56 1.03H22v2h-.56A1.7 1.7 0 0 0 19.4 15Z"/>',
    "back": '<path d="m15 18-6-6 6-6"/><path d="M9 12h12"/>',
    "forward": '<path d="m9 18 6-6-6-6"/><path d="M3 12h12"/>',
    "view": '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/>',
    "command": '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
    "previous": '<path d="m19 20-9-8 9-8v16Z"/><path d="M5 19V5"/>',
    "play": '<path d="m6 3 14 9-14 9V3Z"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "next": '<path d="m5 4 9 8-9 8V4Z"/><path d="M19 5v14"/>',
    "volume": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>',
    "volume-x": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
    "close": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
}

ICON_NAMES = tuple(ICON_SVG)


@lru_cache(maxsize=128)
def icon(name: str, color: str = "#D8DEE9", size: int = 18) -> QIcon:
    """Render one embedded icon as a transparent, cached ``QIcon``."""
    body = ICON_SVG.get(name)
    if body is None:
        return QIcon()

    safe_color = escape(color, quote=True)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{safe_color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))

