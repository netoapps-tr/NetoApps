"""Generate a compact PDF health and capability report for NetOps."""
from __future__ import annotations

import ast
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPORT_VERSION = "1.0"
SKIP_PARTS = {
    ".git", "__pycache__", "build", "dist", ".pytest_cache", ".venv", "venv",
    ".ovos-venv", ".pyapp_build", "site-packages", "node_modules",
}


def _register_font() -> str:
    """Use a Windows Unicode font so Turkish report text renders correctly."""
    font_name = "NetOpsSans"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name
    candidates = (
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
                return font_name
            except Exception:
                continue
    return "Helvetica"


def _project_files(project_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in project_dir.rglob("*.py"):
        try:
            relative = path.relative_to(project_dir)
        except ValueError:
            continue
        if any(part.casefold() in SKIP_PARTS for part in relative.parts):
            continue
        if any(part.startswith("_release_staging") for part in relative.parts):
            continue
        files.append(path)
    return sorted(files)


def _category_for(name: str) -> str:
    value = name.casefold()
    groups = (
        ("Agent ve AI", ("agent", "axvord", "coder", "skill", "adaptive", "ai")),
        ("Arayüz ve hareket", ("ui", "settings", "motion", "sidebar", "experience", "modern")),
        ("Otomasyon", ("automation", "autopilot", "scene", "operation", "reminder", "timer")),
        ("Medya ve Now Playing", ("now_playing", "youtube", "music", "audio", "speech")),
        ("Cihaz ve sistem", ("runtime", "system", "device", "power", "desktop", "windows", "android", "wsl")),
        ("Web ve veri", ("browser", "network", "weather", "public_api")),
        ("Güncelleme ve bakım", ("update", "backup", "doctor", "crash", "dependency")),
        ("Eklenti altyapısı", ("plugin", "builtin")),
    )
    for category, words in groups:
        if any(word in value for word in words):
            return category
    return "Çekirdek ve yardımcı"


def collect_project_catalog(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir).expanduser().resolve()
    categories: dict[str, list[str]] = {}
    syntax_errors: list[str] = []
    total_functions = 0
    total_classes = 0
    for path in _project_files(root):
        relative = str(path.relative_to(root)).replace("\\", "/")
        category = _category_for(path.name)
        categories.setdefault(category, []).append(relative)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"), filename=relative)
            total_functions += sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
            total_classes += sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        except SyntaxError as exc:
            syntax_errors.append(f"{relative}:{exc.lineno or 0}")
        except OSError:
            continue
    return {
        "files": sum(len(items) for items in categories.values()),
        "functions": total_functions,
        "classes": total_classes,
        "categories": {
            key: {"count": len(value), "examples": value[:6]}
            for key, value in sorted(categories.items())
        },
        "syntax_errors": syntax_errors,
    }


def _version(root: Path) -> str:
    path = root / "neto_version.py"
    try:
        match = re.search(r"APP_VERSION\s*=\s*[\"']([^\"']+)", path.read_text(encoding="utf-8-sig"))
        if match:
            return match.group(1)
    except OSError:
        pass
    return "bilinmiyor"


def build_report_data(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir).expanduser().resolve()
    catalog = collect_project_catalog(root)
    try:
        from neto_error_detection_agent import NetOpsErrorDetectionAgent

        errors = NetOpsErrorDetectionAgent(root).run().as_dict()
    except Exception as exc:
        errors = {"ok": False, "error_count": 0, "critical_count": 0, "findings": [], "error": str(exc)}
    try:
        from neto_ui_guard_agent import NetOpsUIGuardAgent

        ui = NetOpsUIGuardAgent(root).run().as_dict()
    except Exception as exc:
        ui = {"ok": False, "error_count": 0, "warning_count": 0, "checks": 0, "errors": [str(exc)], "warnings": []}
    try:
        from neto_skill_loader import discover

        skill_count = len(discover(root))
    except Exception:
        skill_count = 0
    plugins = sorted(path.parent.name for path in (root / "plugins").glob("*/main.py")) if (root / "plugins").is_dir() else []
    nops = sorted(path.name for path in root.glob("*.nops"))
    common_features = [
        ("Sohbet ve bağlam", "Yerel sohbet motoru, düşünme durumu ve bağlama göre skill seçimi", True),
        ("Dosya ve rapor üretimi", "Onaylı metin dosyası ve PDF çıktısı", True),
        ("Hata ve UI denetimi", "Log tarama, kritik hata sayısı ve arayüz sözleşmesi kontrolü", True),
        ("Otomasyon", "Sahneler, zamanlayıcılar, hatırlatıcılar ve autopilot akışı", True),
        ("Cihaz ve sistem", "CPU/RAM, cihaz merkezi, Android ve sistem araçları", True),
        ("Medya", "Now Playing, YouTube Music ve medya atmosferi", True),
        ("Güncelleme ve geri alma", "Güncelleme yardımcıları, yedekleme ve geri alma", True),
        ("Profil ve izinler", "Ayarlar, güvenlik kapıları ve kullanıcı onayı", True),
    ]
    return {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
        "version": _version(root),
        "catalog": catalog,
        "errors": errors,
        "ui": ui,
        "skills": skill_count,
        "plugins": plugins,
        "nops": nops,
        "common_features": common_features,
    }


def _styles(font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("NetOpsTitle", parent=base["Title"], fontName=font, fontSize=24, leading=29, textColor=colors.HexColor("#EAF2FF"), alignment=TA_LEFT, spaceAfter=6),
        "subtitle": ParagraphStyle("NetOpsSubtitle", parent=base["Normal"], fontName=font, fontSize=10, leading=14, textColor=colors.HexColor("#94A7C6"), spaceAfter=16),
        "h1": ParagraphStyle("NetOpsH1", parent=base["Heading1"], fontName=font, fontSize=15, leading=20, textColor=colors.HexColor("#55A5FF"), spaceBefore=12, spaceAfter=8),
        "body": ParagraphStyle("NetOpsBody", parent=base["BodyText"], fontName=font, fontSize=9.5, leading=14, textColor=colors.HexColor("#E7EDF8"), spaceAfter=5),
        "small": ParagraphStyle("NetOpsSmall", parent=base["BodyText"], fontName=font, fontSize=8, leading=11, textColor=colors.HexColor("#9CAECC")),
        "cell": ParagraphStyle("NetOpsCell", parent=base["BodyText"], fontName=font, fontSize=8.5, leading=11, textColor=colors.HexColor("#E7EDF8")),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>") , style)


def _group_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (str(finding.get("severity", "")), str(finding.get("message", "")))
        item = grouped.setdefault(key, {"severity": key[0], "message": key[1], "count": 0, "source": finding.get("source", ""), "line": finding.get("line", 0)})
        item["count"] += 1
    return sorted(grouped.values(), key=lambda item: (item["severity"] != "critical", -item["count"], item["message"]))


def write_report_pdf(project_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_dir).expanduser().resolve()
    data = build_report_data(root)
    target = Path(output_path).expanduser().resolve() if output_path else Path.home() / "Desktop" / "NetOps_Rapor.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    font = _register_font()
    styles = _styles(font)
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=15 * mm,
        title="NetOps Teknik Durum Raporu",
        author="NetOps",
    )
    story: list[Any] = []
    story.append(_p("NETOPS HARBILIG", styles["title"]))
    story.append(_p(f"Teknik durum, hata ve özellik envanteri · v{data['version']} · {data['generated_at']}", styles["subtitle"]))

    errors = data["errors"]
    ui = data["ui"]
    summary_rows = [
        [_p("Kod dosyası", styles["cell"]), _p(data["catalog"]["files"], styles["cell"]), _p("Fonksiyon", styles["cell"]), _p(data["catalog"]["functions"], styles["cell"])],
        [_p("Sınıf", styles["cell"]), _p(data["catalog"]["classes"], styles["cell"]), _p("Proje skill'i", styles["cell"]), _p(data["skills"], styles["cell"])],
        [_p("Log hatası", styles["cell"]), _p(errors.get("error_count", 0), styles["cell"]), _p("Kritik hata", styles["cell"]), _p(errors.get("critical_count", 0), styles["cell"])],
        [_p("UI kontrolü", styles["cell"]), _p("Temiz" if ui.get("ok") else "Bulgulu", styles["cell"]), _p("Eklenti", styles["cell"]), _p(len(data["plugins"]), styles["cell"])],
    ]
    summary = Table(summary_rows, colWidths=[32 * mm, 28 * mm, 32 * mm, 28 * mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#151D2B")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#30435F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(summary)
    story.append(_p("Bu rapor NetOps kaynak klasöründeki modülleri, logları ve UI sözleşmelerini özetler. Kod değişikliği yapmaz.", styles["body"]))

    story.append(_p("Mevcut yetenek alanları", styles["h1"]))
    capability_rows = [[_p("Alan", styles["cell"]), _p("Modül sayısı", styles["cell"]), _p("Örnekler", styles["cell"])]]
    for category, info in data["catalog"]["categories"].items():
        examples = ", ".join(info["examples"][:4])
        capability_rows.append([_p(category, styles["cell"]), _p(info["count"], styles["cell"]), _p(examples, styles["cell"])])
    capability = Table(capability_rows, colWidths=[43 * mm, 23 * mm, 89 * mm], repeatRows=1)
    capability.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F6FEB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#151D2B")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#30435F")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(capability)

    story.append(_p("Genellikle iyi masaüstü asistanlarında bulunan temel alanlar", styles["h1"]))
    feature_rows = [[_p("Alan", styles["cell"]), _p("Beklenen işlev", styles["cell"]), _p("NetOps", styles["cell"])]]
    for name, description, present in data["common_features"]:
        feature_rows.append([_p(name, styles["cell"]), _p(description, styles["cell"]), _p("Var" if present else "Eksik", styles["cell"])])
    feature_table = Table(feature_rows, colWidths=[42 * mm, 99 * mm, 18 * mm], repeatRows=1)
    feature_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F6FEB")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#151D2B")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#30435F")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(feature_table)

    story.append(PageBreak())
    story.append(_p("Hata ve kalite durumu", styles["h1"]))
    findings = _group_findings(errors.get("findings") or [])
    if findings:
        finding_rows = [[_p("Seviye", styles["cell"]), _p("Kaynak", styles["cell"]), _p("Mesaj", styles["cell"])]]
        for finding in findings[:24]:
            count = f" ({finding.get('count', 1)} kez)" if finding.get("count", 1) > 1 else ""
            finding_rows.append([_p(finding.get("severity", ""), styles["cell"]), _p(f"{finding.get('source', '')}:{finding.get('line', '')}", styles["cell"]), _p(f"{finding.get('message', '')}{count}", styles["cell"])])
        finding_table = Table(finding_rows, colWidths=[24 * mm, 46 * mm, 89 * mm], repeatRows=1)
        finding_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B42318")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#241A20")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#5B3340")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(finding_table)
    else:
        story.append(_p("Son log taramasında raporlanabilir hata bulunmadı.", styles["body"]))
    if data["catalog"]["syntax_errors"]:
        story.append(_p("Python sözdizimi bulguları: " + ", ".join(data["catalog"]["syntax_errors"]), styles["body"]))
    story.append(_p("UI durumu", styles["h1"]))
    story.append(_p(f"{ui.get('checks', 0)} kontrol çalıştı · {ui.get('error_count', 0)} hata · {ui.get('warning_count', 0)} uyarı", styles["body"]))
    for item in (ui.get("errors") or [])[:8]:
        story.append(_p("- " + item, styles["small"]))
    story.append(_p("Test planı", styles["h1"]))
    for item in (
        "PDF komutu masaüstünde NetOps_Rapor.pdf oluşturmalı.",
        "Aynı dosya tekrar yazılmadan önce kullanıcıya açık davranış gösterilmeli.",
        "Hata sayısı ve kritik hata sayısı log taramasıyla doğrulanmalı.",
        "UI kontrolü ve Python derleme testleri güncelleme öncesi çalıştırılmalı.",
    ):
        story.append(_p("- " + item, styles["body"]))

    def paint_page(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0B1019"))
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        canvas.setStrokeColor(colors.HexColor("#1F6FEB"))
        canvas.setLineWidth(1)
        canvas.line(17 * mm, A4[1] - 12 * mm, A4[0] - 17 * mm, A4[1] - 12 * mm)
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#8194B2"))
        canvas.drawString(17 * mm, 8 * mm, "NetOps Harbilig · yerel teknik rapor")
        canvas.drawRightString(A4[0] - 17 * mm, 8 * mm, f"Sayfa {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=paint_page, onLaterPages=paint_page)
    return {"ok": True, "path": str(target), "data": data}


__all__ = ["build_report_data", "collect_project_catalog", "write_report_pdf"]
