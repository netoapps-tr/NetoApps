"""Font-independent, fixed-size line icons for the NetOps sidebar."""
from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw


ICONS = {
    "btn_now_playing_ayar": "sliders",
    "btn_now_playing_baslat": "music",
    "btn_netoai": "chat",
    "btn_android_device": "remote",
    "btn_automation": "workflow",
    "btn_scenes": "layers",
    "btn_profiles": "user",
    "btn_reminders": "bell",
    "btn_anahtar": "power",
    "btn_store_panel": "store",
}


@lru_cache(maxsize=64)
def icon(kind, size=22):
    def draw_icon(color):
        scale = 4
        image = Image.new("RGBA", (96, 96))
        d = ImageDraw.Draw(image)

        def box(coords):
            return tuple(round(v * scale) for v in coords)

        def line(*points):
            d.line([tuple(round(v * scale) for v in p) for p in points],
                   fill=color, width=7, joint="curve")

        def rect(coords, radius=2):
            d.rounded_rectangle(box(coords), radius=radius * scale,
                                outline=color, width=7)

        def oval(coords):
            d.ellipse(box(coords), outline=color, width=7)

        if kind == "sliders":
            for y, x in ((5, 8), (12, 16), (19, 10)):
                line((3, y), (x-2, y)); line((x+2, y), (21, y))
                oval((x-2, y-2, x+2, y+2))
        elif kind == "music":
            line((9, 17), (9, 5), (20, 3), (20, 15))
            line((9, 9), (20, 7))
            oval((3, 16, 9, 21)); oval((14, 14, 20, 19))
        elif kind == "chat":
            line((7, 19), (3, 22), (3, 6), (5, 3), (19, 3),
                 (21, 5), (21, 17), (19, 19), (7, 19))
            line((7, 8), (17, 8)); line((7, 13), (14, 13))
        elif kind == "devices":
            rect((2, 3, 16, 15)); line((8, 15), (8, 20), (3, 20))
            rect((14, 9, 22, 22)); line((17, 19), (19, 19))
        elif kind == "remote":
            oval((2, 9, 8, 15)); oval((16, 9, 22, 15)); oval((9, 2, 15, 8))
            line((8, 11), (16, 11)); line((9, 8), (7, 10)); line((15, 8), (17, 10))
        elif kind == "workflow":
            rect((8, 2, 16, 8)); rect((2, 16, 9, 22)); rect((15, 16, 22, 22))
            line((12, 8), (12, 12), (5, 12), (5, 16))
            line((12, 12), (19, 12), (19, 16))
        elif kind == "layers":
            line((2, 8), (12, 2), (22, 8), (12, 14), (2, 8))
            line((2, 13), (12, 19), (22, 13))
            line((5, 19), (12, 23), (19, 19))
        elif kind == "user":
            oval((8, 2, 16, 10))
            d.arc(box((3, 13, 21, 29)), 180, 360, fill=color, width=7)
            line((3, 21), (21, 21))
        elif kind == "bell":
            line((3, 18), (6, 14), (6, 8), (8, 4), (12, 2),
                 (16, 4), (18, 8), (18, 14), (21, 18), (3, 18))
            d.arc(box((9, 18, 15, 23)), 0, 180, fill=color, width=7)
        elif kind == "power":
            d.arc(box((3, 3, 21, 21)), -50, 230, fill=color, width=7)
            line((12, 2), (12, 12))
        elif kind == "store":
            rect((4, 8, 20, 22)); line((8, 8), (8, 3), (16, 3), (16, 8))
        elif kind == "panel":
            rect((2, 3, 22, 21)); line((9, 3), (9, 21))
        elif kind == "settings":
            oval((4, 4, 20, 20)); oval((9, 9, 15, 15))
            for a, b in (((12, 1), (12, 5)), ((12, 19), (12, 23)),
                         ((1, 12), (5, 12)), ((19, 12), (23, 12)),
                         ((4, 4), (7, 7)), ((17, 17), (20, 20)),
                         ((4, 20), (7, 17)), ((17, 7), (20, 4))):
                line(a, b)
        return image.resize((size * 2, size * 2), Image.Resampling.LANCZOS)

    return ctk.CTkImage(light_image=draw_icon("#35404C"),
                       dark_image=draw_icon("#D0D5DB"), size=(size, size))


def apply(widget, name, label, compact):
    if name not in ICONS:
        return False
    from neto_experience3 import Tooltip
    widget._neto_modern_skip = True
    widget.configure(image=icon(ICONS[name]), text="" if compact else label,
                     compound="left", anchor="center" if compact else "w")
    tip = getattr(widget, "_neto_sidebar_tip", None)
    if tip is None:
        tip = widget._neto_sidebar_tip = Tooltip(widget, label)
        widget.bind("<Destroy>", tip._hide, add="+")
    tip.text = label
    return True
