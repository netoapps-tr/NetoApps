from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image

SCHEMA_VERSION = 1
MARKER_NAME = "onboarding_complete_v1.json"
ASSET_DIR_NAME = "neto_onboarding_assets"

TR_PAGES = [
    {
        "eyebrow": "YENİ ARAYÜZ",
        "title": "NetOps Experience",
        "description": "Neto'nun yeni arayüzü daha sade, daha hızlı ve günlük kullanım için daha akıcı.",
        "bullets": ["Modern koyu tasarım", "Daha hızlı erişim", "Tek merkezden tüm özellikler"],
        "image": "01_neto_experience.png",
    },
    {
        "eyebrow": "HOŞ GELDİN",
        "title": "NetOps'u\nKullanmaya Başlayın",
        "description": "Neto, günlük işlerinizde size yardımcı olmak için hazır. Sohbet edin, komut verin ve araçları kullanın.",
        "bullets": ["Akıllı sohbet", "Sesli komutlar", "Yapay zekâ destekli araçlar"],
        "image": "02_welcome.png",
    },
    {
        "eyebrow": "AKILLI SOHBET",
        "title": "Doğal ve Hızlı\nYanıtlar",
        "description": "Sorularınızı doğal bir dille yazın. Neto konuşmanın bağlamını takip eder ve anlaşılır yanıtlar üretir.",
        "bullets": ["Doğal dil desteği", "Konuşma bağlamını hatırlama", "Türkçe ve İngilizce kullanım"],
        "image": "03_chat.png",
    },
    {
        "eyebrow": "LIVE MODE",
        "title": "Sesli Komutlar\nve Yanıtlar",
        "description": "Mikrofona konuşun; Neto söylediklerinizi algılasın, işlemi gerçekleştirsin ve sesli yanıt versin.",
        "bullets": ["Mikrofondan komut", "Sesli yanıt", "Canlı konuşma deneyimi"],
        "image": "04_voice.png",
    },
    {
        "eyebrow": "AKILLI ARAÇLAR",
        "title": "İşlerinizi Tek\nYerden Yönetin",
        "description": "Araştırma, metin üretme, kod, dosya ve sistem işlemlerinde Neto'nun araçlarından yararlanın.",
        "bullets": ["Araştırma ve bilgi", "Metin ve kod işlemleri", "Sistem araçları"],
        "image": "05_tools.png",
    },
    {
        "eyebrow": "HAZIRSIN",
        "title": "Haydi\nBaşlayalım!",
        "description": "Neto ile tanışma tamamlandı. Ana arayüze geçerek tüm özellikleri kullanmaya başlayabilirsiniz.",
        "bullets": ["Sorularınızı sorun", "İşlerinizi kolaylaştırın", "Zamandan tasarruf edin"],
        "image": "06_finish.png",
    },
]

EN_PAGES = [
    {
        "eyebrow": "NEW INTERFACE",
        "title": "NetOps Experience",
        "description": "Neto's new interface is cleaner, faster and more fluid for everyday use.",
        "bullets": ["Modern dark design", "Faster access", "Every feature in one place"],
        "image": "01_neto_experience.png",
    },
    {
        "eyebrow": "WELCOME",
        "title": "Start Using\nNetOps",
        "description": "Neto is ready to help with everyday tasks. Chat, issue commands and use smart tools.",
        "bullets": ["Intelligent chat", "Voice commands", "AI-powered tools"],
        "image": "02_welcome.png",
    },
    {
        "eyebrow": "SMART CHAT",
        "title": "Natural and\nFast Answers",
        "description": "Ask questions naturally. Neto follows the conversation and produces clear answers.",
        "bullets": ["Natural language", "Conversation context", "Turkish and English"],
        "image": "03_chat.png",
    },
    {
        "eyebrow": "LIVE MODE",
        "title": "Voice Commands\nand Answers",
        "description": "Speak into the microphone. Neto can understand, perform the task and answer aloud.",
        "bullets": ["Microphone commands", "Spoken responses", "Live conversation"],
        "image": "04_voice.png",
    },
    {
        "eyebrow": "SMART TOOLS",
        "title": "Manage Tasks\nin One Place",
        "description": "Use Neto for research, writing, code, files and system operations.",
        "bullets": ["Research and information", "Writing and code", "System tools"],
        "image": "05_tools.png",
    },
    {
        "eyebrow": "READY",
        "title": "Let's\nGet Started!",
        "description": "The introduction is complete. Continue to the main interface and start using Neto.",
        "bullets": ["Ask questions", "Simplify tasks", "Save time"],
        "image": "06_finish.png",
    },
]

def _data_dir() -> Path:
    override = os.environ.get("NETO_ONBOARDING_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "NetoAssistant" / "installation"
    return Path.home() / "AppData" / "Local" / "NetoAssistant" / "installation"

def marker_path() -> Path:
    return _data_dir() / MARKER_NAME

def onboarding_completed() -> bool:
    if os.environ.get("NETO_FORCE_ONBOARDING", "").strip() == "1":
        return False
    try:
        return marker_path().is_file()
    except Exception:
        return False

def reset_onboarding() -> bool:
    try:
        marker_path().unlink(missing_ok=True)
        return True
    except Exception:
        return False

def _write_marker(state: str = "completed") -> None:
    try:
        folder = _data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        marker = marker_path()
        temp = marker.with_suffix(marker.suffix + ".tmp")
        payload: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "state": state,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, marker)
    except Exception:
        try:
            marker_path().parent.mkdir(parents=True, exist_ok=True)
            marker_path().touch(exist_ok=True)
        except Exception:
            pass

def _asset_path(filename: str, get_asset_path=None) -> Path:
    candidates = [
        Path(__file__).resolve().parent / ASSET_DIR_NAME / filename,
        Path.cwd() / ASSET_DIR_NAME / filename,
    ]
    if callable(get_asset_path):
        try:
            candidates.insert(0, Path(str(get_asset_path(filename))))
        except Exception:
            pass
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return candidates[0]

def show_onboarding_if_needed(
    *,
    win,
    root,
    get_asset_path=None,
    lang: str = "tr",
    on_complete: Callable[[], None] | None = None,
) -> bool:
    if onboarding_completed():
        return False

    pages = TR_PAGES if str(lang or "tr").lower().startswith("tr") else EN_PAGES
    labels = (
        {"skip": "Atla", "back": "Geri", "next": "İleri", "finish": "Neto'yu Başlat", "page": "Tanıtım"}
        if pages is TR_PAGES
        else {"skip": "Skip", "back": "Back", "next": "Next", "finish": "Start Neto", "page": "Introduction"}
    )

    state = {"index": 0, "finished": False, "images": [], "jobs": set()}

    def safe_exists(widget) -> bool:
        try:
            return bool(widget is not None and widget.winfo_exists())
        except Exception:
            return False

    def cancel_jobs() -> None:
        for job in list(state["jobs"]):
            try:
                win.after_cancel(job)
            except Exception:
                pass
        state["jobs"].clear()

    def schedule(delay: int, callback) -> None:
        try:
            holder = {"id": None}
            def wrapped():
                job_id = holder["id"]
                state["jobs"].discard(job_id)
                if not state["finished"] and safe_exists(win):
                    callback()
            holder["id"] = win.after(delay, wrapped)
            state["jobs"].add(holder["id"])
        except Exception:
            pass

    def finish(mark_complete: bool = True) -> None:
        if state["finished"]:
            return
        state["finished"] = True
        cancel_jobs()
        if mark_complete:
            _write_marker("completed")
        if callable(on_complete):
            try:
                on_complete()
            except Exception as exc:
                try:
                    print(f"[ONBOARDING_COMPLETE_ERROR] {exc}", flush=True)
                except Exception:
                    pass

    try:
        for child in list(win.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
    except Exception:
        return False

    try:
        win.title("NetOps Experience")
        win.resizable(False, False)
        win.configure(fg_color="#05050b")
        width, height = 980, 610
        win.geometry(f"{width}x{height}")
        win.update_idletasks()
        screen_w = max(width, int(win.winfo_screenwidth()))
        screen_h = max(height, int(win.winfo_screenheight()))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 10)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.lift()
        win.focus_force()
        win.grab_set()
    except Exception:
        pass

    outer = ctk.CTkFrame(win, fg_color="#070710", corner_radius=28, border_width=1, border_color="#26243a")
    outer.pack(fill="both", expand=True, padx=14, pady=14)

    header = ctk.CTkFrame(outer, fg_color="transparent", height=54)
    header.pack(fill="x", padx=28, pady=(16, 0))
    header.pack_propagate(False)

    ctk.CTkLabel(
        header,
        text="NETO EXPERIENCE",
        font=("Segoe UI Semibold", 13),
        text_color="#8d67ff",
    ).pack(side="left", pady=12)

    page_count = ctk.CTkLabel(
        header,
        text="",
        font=("Segoe UI", 12),
        text_color="#6f6f86",
    )
    page_count.pack(side="right", pady=12)

    body = ctk.CTkFrame(outer, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=28, pady=(4, 14))
    body.grid_columnconfigure(0, weight=13)
    body.grid_columnconfigure(1, weight=11)
    body.grid_rowconfigure(0, weight=1)

    visual_panel = ctk.CTkFrame(body, fg_color="#090918", corner_radius=24, border_width=1, border_color="#292544")
    visual_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 13))

    visual_glow = ctk.CTkFrame(visual_panel, fg_color="#0b0920", corner_radius=22)
    visual_glow.pack(fill="both", expand=True, padx=12, pady=12)

    image_label = ctk.CTkLabel(visual_glow, text="")
    image_label.place(relx=0.5, rely=0.5, anchor="center")

    content = ctk.CTkFrame(body, fg_color="transparent")
    content.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
    content.grid_columnconfigure(0, weight=1)

    eyebrow = ctk.CTkLabel(content, text="", font=("Segoe UI Semibold", 13), text_color="#8d67ff", anchor="w")
    eyebrow.grid(row=0, column=0, sticky="ew", pady=(54, 10))

    title = ctk.CTkLabel(
        content,
        text="",
        font=("Segoe UI Semibold", 34),
        text_color="#f7f6ff",
        anchor="w",
        justify="left",
        wraplength=390,
    )
    title.grid(row=1, column=0, sticky="ew")

    description = ctk.CTkLabel(
        content,
        text="",
        font=("Segoe UI", 15),
        text_color="#aaa8bc",
        anchor="w",
        justify="left",
        wraplength=380,
    )
    description.grid(row=2, column=0, sticky="ew", pady=(16, 16))

    bullets_frame = ctk.CTkFrame(content, fg_color="transparent")
    bullets_frame.grid(row=3, column=0, sticky="ew")

    bullet_labels = []
    for row in range(3):
        item = ctk.CTkLabel(
            bullets_frame,
            text="",
            font=("Segoe UI", 14),
            text_color="#d9d7e8",
            anchor="w",
            justify="left",
        )
        item.grid(row=row, column=0, sticky="ew", pady=4)
        bullet_labels.append(item)

    footer = ctk.CTkFrame(outer, fg_color="#080812", height=74, corner_radius=22)
    footer.pack(fill="x", padx=28, pady=(0, 22))
    footer.pack_propagate(False)

    skip_button = ctk.CTkButton(
        footer,
        text=labels["skip"],
        width=90,
        height=40,
        corner_radius=15,
        fg_color="#11111d",
        hover_color="#1a192a",
        border_width=1,
        border_color="#2b2940",
        text_color="#aaa8bd",
        command=lambda: finish(True),
    )
    skip_button.pack(side="left", padx=(16, 6), pady=17)

    back_button = ctk.CTkButton(
        footer,
        text=labels["back"],
        width=90,
        height=40,
        corner_radius=15,
        fg_color="#11111d",
        hover_color="#1a192a",
        border_width=1,
        border_color="#2b2940",
        text_color="#e5e3f2",
    )
    back_button.pack(side="left", padx=6, pady=17)

    dots_frame = ctk.CTkFrame(footer, fg_color="transparent")
    dots_frame.pack(side="left", expand=True)

    dots = []
    for _ in pages:
        dot = ctk.CTkFrame(dots_frame, width=9, height=9, corner_radius=5, fg_color="#3d3b50")
        dot.pack(side="left", padx=4)
        dot.pack_propagate(False)
        dots.append(dot)

    next_button = ctk.CTkButton(
        footer,
        text=labels["next"],
        width=145,
        height=42,
        corner_radius=16,
        fg_color="#5b2dff",
        hover_color="#7248ff",
        text_color="#ffffff",
        font=("Segoe UI Semibold", 13),
    )
    next_button.pack(side="right", padx=(8, 16), pady=16)

    def load_image(filename: str):
        path = _asset_path(filename, get_asset_path)
        try:
            picture = Image.open(path).convert("RGBA")
            return ctk.CTkImage(light_image=picture, dark_image=picture, size=(405, 405))
        except Exception:
            return None

    def render(index: int) -> None:
        index = max(0, min(len(pages)-1, index))
        state["index"] = index
        page = pages[index]

        page_count.configure(text=f"{labels['page']}  {index + 1} / {len(pages)}")
        eyebrow.configure(text=page["eyebrow"])
        title.configure(text=page["title"])
        description.configure(text=page["description"])

        for label_widget, text in zip(bullet_labels, page["bullets"]):
            label_widget.configure(text=f"✓  {text}")

        picture = load_image(page["image"])
        if picture is not None:
            state["images"].append(picture)
            if len(state["images"]) > 8:
                state["images"] = state["images"][-8:]
            image_label.configure(image=picture, text="")
            setattr(image_label, "image", picture)
        else:
            image_label.configure(image="", text="N", font=("Segoe UI Semibold", 92), text_color="#7048ff")

        for dot_index, dot in enumerate(dots):
            dot.configure(
                fg_color="#7b51ff" if dot_index == index else "#3d3b50",
                width=24 if dot_index == index else 9,
            )

        back_button.configure(
            state="normal" if index > 0 else "disabled",
            fg_color="#11111d" if index > 0 else "#0c0c14",
        )
        next_button.configure(
            text=labels["finish"] if index == len(pages)-1 else labels["next"],
            width=165 if index == len(pages)-1 else 145,
        )

    def go_back() -> None:
        if state["index"] > 0:
            render(state["index"] - 1)

    def go_next() -> None:
        if state["index"] >= len(pages)-1:
            finish(True)
        else:
            render(state["index"] + 1)

    back_button.configure(command=go_back)
    next_button.configure(command=go_next)

    try:
        win.bind("<Left>", lambda _event: go_back(), add="+")
        win.bind("<Right>", lambda _event: go_next(), add="+")
        win.bind("<Return>", lambda _event: go_next(), add="+")
        win.bind("<Escape>", lambda _event: finish(True), add="+")
    except Exception:
        pass

    render(0)
    schedule(80, lambda: win.focus_force())
    return True

__all__ = [
    "MARKER_NAME",
    "marker_path",
    "onboarding_completed",
    "reset_onboarding",
    "show_onboarding_if_needed",
]
