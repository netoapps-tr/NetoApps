from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox


# browser_engine.py içindeki neto_browser_ac, __main__ üzerinden
# eklenti_aktif_mi ve geri bildirim fonksiyonlarını okuyor.
eklenti_aktif_mi = True


def _show_message(text: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Neto Browser", text, parent=root)
        root.destroy()
    except Exception:
        pass


def animasyonlu_yazi(metin: str) -> None:
    if metin:
        _show_message(str(metin))


def ses_oynat(*args, **kwargs) -> None:
    return None


def main() -> int:
    from browser_engine import neto_browser_ac

    url = "https://www.google.com"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        url = sys.argv[1].strip()

    neto_browser_ac(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
