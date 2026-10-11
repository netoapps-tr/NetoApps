"""Small, interruptible CTk transitions that never change widget geometry."""
from collections import deque

import customtkinter as ctk

from neto_motion_engine_v2 import get_motion_engine, interpolate_color


def color_value(widget, value):
    if isinstance(value, (tuple, list)):
        value = value[1 if ctk.get_appearance_mode() == "Dark" else 0]
    if value == "transparent":
        parent = getattr(widget, "master", None)
        if parent is not None:
            return color_value(parent, parent.cget("fg_color"))
    return str(value)


class HoverMotion:
    def __init__(self, widget, engine):
        self.widget, self.engine = widget, engine
        self.key = f"hover:{id(widget)}"
        self.inside = False
        self.base = widget.cget("fg_color")
        self.last = self.base
        widget.bind("<Enter>", lambda _e: self.set_hovered(True), add="+")
        widget.bind("<Leave>", lambda _e: self.set_hovered(False), add="+")
        widget.bind("<Destroy>", self.destroy, add="+")

    def set_hovered(self, inside):
        w = self.widget
        if not w.winfo_exists() or w.cget("state") == "disabled":
            return
        current = w.cget("fg_color")
        if current != self.last:
            # A theme change or selected navigation button sets a new base.
            self.base = current
        if self.inside == inside and current == self.last:
            return
        self.inside = inside
        start = color_value(w, current)
        target = color_value(w, w.cget("hover_color") if inside else self.base)

        def update(progress):
            if not w.winfo_exists():
                self.engine.cancel(self.key)
                return
            value = self.base if not inside and progress >= 1 else interpolate_color(start, target, progress)
            if value != self.last:
                self.last = value
                w.configure(fg_color=value)

        self.engine.tween(self.key, 140 if inside else 180, update)

    def destroy(self, event):
        if event.widget is self.widget:
            self.engine.cancel(self.key)

    def reset(self):
        self.engine.cancel(self.key)
        if self.widget.winfo_exists():
            self.widget.configure(fg_color=self.base)
            self.last = self.base
        self.inside = False


def bind_hover(widget, root):
    current = getattr(widget, "_neto_hover_controller", None)
    if current is not None:
        return current
    if getattr(widget, "_neto_custom_motion", False):
        return None
    if isinstance(widget, ctk.CTkButton):
        current = HoverMotion(widget, get_motion_engine(root))
        widget._neto_hover_controller = current
    return current


def bind_hover_tree(parent, root, limit=900):
    pending = deque([parent])
    for _ in range(limit):
        if not pending:
            break
        widget = pending.popleft()
        try:
            pending.extend(widget.winfo_children())
            bind_hover(widget, root)
        except (AttributeError, ValueError):
            continue


def reset_hover_tree(parent):
    pending = [parent]
    while pending:
        widget = pending.pop()
        try:
            pending.extend(widget.winfo_children())
            controller = getattr(widget, "_neto_hover_controller", None)
            if controller is not None:
                controller.reset()
        except Exception:
            continue


def slide_surface(root, surface, *, closing=False, done=None, key="page-transition"):
    engine = get_motion_engine(root)
    active = key in engine._jobs
    engine.cancel(key)
    if not surface.winfo_exists():
        if callable(done):
            done()
        return
    info = surface.place_info()
    start = int(float(info.get("y") or 0)) if active or closing else 12
    end = 12 if closing else 0
    surface.place_configure(y=start)
    last = [start]

    def update(progress):
        if not surface.winfo_exists():
            engine.cancel(key)
            return
        y = round(start + (end - start) * progress)
        if y != last[0]:
            surface.place_configure(y=y)
            last[0] = y

    engine.tween(key, 160 if closing else 220, update, on_complete=done)
