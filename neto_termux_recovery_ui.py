"""Small dependency-free Recovery confirmation screen for Termux."""
from __future__ import annotations

import sys
from typing import Callable


OPTIONS = ("onayla", "iptal")


def normalize_choice(value: str) -> str | None:
    normalized = str(value or "").strip().casefold()
    return {
        "1": "onayla",
        "onayla": "onayla",
        "evet": "onayla",
        "2": "iptal",
        "iptal": "iptal",
        "hayır": "iptal",
        "hayir": "iptal",
        "esc": "iptal",
    }.get(normalized)


def recovery_screen_lines(selected: int = 0) -> list[str]:
    selected = 0 if int(selected) <= 0 else 1
    choices = []
    for index, label in enumerate(("ONAYLA", "İPTAL")):
        marker = "[>]" if index == selected else "[ ]"
        choices.append(f"  {marker} {index + 1}. {label}")
    return [
        "",
        "==============================",
        "       RECOVERY NETOPS        ",
        "==============================",
        "",
        "Ana NetOps ekranı gizlenecek.",
        "Recovery modu güvenli olarak açılacak.",
        "",
        *choices,
        "",
        "Yukarı/aşağı: seç  |  Enter: uygula  |  Esc: iptal",
    ]


def choose_recovery_action(*, output: Callable[[str], None] = print) -> str | None:
    """Show a keyboard-driven phone screen and return ``onayla`` or ``iptal``."""
    if not sys.stdin.isatty():
        return None
    try:
        import curses

        def screen(stdscr):
            curses.curs_set(0)
            stdscr.keypad(True)
            selected = 0
            while True:
                stdscr.erase()
                height, width = stdscr.getmaxyx()
                lines = recovery_screen_lines(selected)
                start_y = max(0, (height - len(lines)) // 2)
                for offset, line in enumerate(lines):
                    try:
                        stdscr.addstr(start_y + offset, max(0, (width - len(line)) // 2), line[: max(1, width - 1)])
                    except curses.error:
                        pass
                stdscr.refresh()
                key = stdscr.getch()
                if key in (curses.KEY_UP, ord("k")):
                    selected = 0
                elif key in (curses.KEY_DOWN, ord("j")):
                    selected = 1
                elif key in (10, 13, curses.KEY_ENTER):
                    return OPTIONS[selected]
                elif key in (27, ord("q")):
                    return "iptal"

        return curses.wrapper(screen)
    except (ImportError, OSError):
        output("Recovery onayı: 1=ONAYLA, 2=İPTAL")
        try:
            return normalize_choice(input("Seçiminiz: "))
        except (EOFError, KeyboardInterrupt):
            return "iptal"


__all__ = ["OPTIONS", "choose_recovery_action", "normalize_choice", "recovery_screen_lines"]
