from __future__ import annotations

import customtkinter as ctk

from neto_automation_ui import create_automation_panel

try:
    from neto_branding import apply_window_icon as _neto_apply_window_icon
except Exception:
    _neto_apply_window_icon = None


def apply_window_icon(*args, **kwargs) -> bool:
    func = _neto_apply_window_icon
    if callable(func):
        return bool(func(*args, **kwargs))
    return False


def main() -> None:
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("Neto Otomasyon Merkezi")
    root.geometry("1280x820")
    root.minsize(960, 650)
    apply_window_icon(root)
    create_automation_panel(root, root=root)
    root.mainloop()


if __name__ == "__main__":
    main()
