"""Create the Turkish NetOps 1.52 assistant and feature report PDF."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "pdf" / "NetOps_Asistan_Ozellikleri_1.52.pdf"
PAGE = A4
BG = colors.HexColor("#0A0D14")
SURFACE = colors.HexColor("#121722")
SURFACE_ALT = colors.HexColor("#171E2D")
LINE = colors.HexColor("#2C3A53")
ACCENT = colors.HexColor("#4D8DFF")
ACCENT_SOFT = colors.HexColor("#8FB6FF")
TEXT = colors.HexColor("#EAF1FF")
MUTED = colors.HexColor("#9EADCA")
GREEN = colors.HexColor("#4FD18B")
AMBER = colors.HexColor("#F4C66D")


def register_font() -> str:
    name = "NetOpsReportSans"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = (
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
        Path(r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                pdfmetrics.registerFont(TTFont(name, str(candidate)))
                return name
            except Exception:
                continue
    return "Helvetica"


def styles(font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName=font, fontSize=28,
            leading=33, textColor=TEXT, alignment=TA_LEFT, spaceAfter=7,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName=font, fontSize=11,
            leading=16, textColor=MUTED, spaceAfter=15,
        ),
        "h1": ParagraphStyle(
            "ReportH1", parent=base["Heading1"], fontName=font, fontSize=17,
            leading=22, textColor=ACCENT_SOFT, spaceBefore=4, spaceAfter=9,
        ),
        "h2": ParagraphStyle(
            "ReportH2", parent=base["Heading2"], fontName=font, fontSize=11,
            leading=15, textColor=TEXT, spaceBefore=4, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontName=font, fontSize=9.5,
            leading=14, textColor=TEXT, spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "ReportSmall", parent=base["BodyText"], fontName=font, fontSize=8,
            leading=11, textColor=MUTED, spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "ReportCell", parent=base["BodyText"], fontName=font, fontSize=8.4,
            leading=11.5, textColor=TEXT,
        ),
        "cell_muted": ParagraphStyle(
            "ReportCellMuted", parent=base["BodyText"], fontName=font, fontSize=8.2,
            leading=11, textColor=MUTED,
        ),
        "status": ParagraphStyle(
            "ReportStatus", parent=base["BodyText"], fontName=font, fontSize=8.4,
            leading=11, textColor=GREEN,
        ),
        "center": ParagraphStyle(
            "ReportCenter", parent=base["BodyText"], fontName=font, fontSize=9,
            leading=13, textColor=TEXT, alignment=TA_CENTER,
        ),
    }


def p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)


def rich(value: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(value, style)


def table(rows: list[list[object]], widths: list[float], *, header: bool = True) -> Table:
    converted = []
    for row_index, row in enumerate(rows):
        converted.append([
            item if isinstance(item, Paragraph) else p(item, _TABLE_STYLES["cell"])
            for item in row
        ])
    result = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1 if header else 0), (-1, -1), SURFACE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if not header:
        commands = [
            ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    result.setStyle(TableStyle(commands))
    return result


_TABLE_STYLES: dict[str, ParagraphStyle] = {}


def feature_rows() -> list[list[str]]:
    return [
        ["Yetenek alanı", "Mevcut davranış", "Durum"],
        ["Sohbet asistanı", "NetOps sohbet motoruna bağlı; yanıtlar arka planda hazırlanırken arayüz donmaz.", "Hazır"],
        ["Yerel skill sistemi", "Sistem, medya, cihazlar, yardım ve Recovery Mesh yerleşik skill alanları; SKILL.md keşfi.", "Hazır"],
        ["Sistem durumu", "CPU, RAM, GPU, cihaz sayısı ve Remote durumu arayüzde izlenir; 1 saniyelik yenileme döngüsü.", "Hazır"],
        ["Cihazlar", "Bağlı cihazları tablo halinde gösterir ve cihaz merkezine bağlanır.", "Hazır"],
        ["Remote", "Telefon ve Termux bağlantıları için ayrı yüzey ve güvenli callback altyapısı.", "Bağlanabilir"],
        ["Otomasyonlar", "Otomasyonları ve çalışma akışlarını görüntüleme ve yenileme yüzeyi.", "Hazır"],
        ["Bildirimler", "NetOps olaylarının ve cihaz bildirimlerinin ayrı akış ekranı.", "Hazır"],
        ["Ayarlar", "Dil, tema, görünüm, güvenlik, güncelleme ve açılış davranışları.", "Hazır"],
        ["Dosya ve rapor", "Onay akışıyla dosya üretimi ve PDF rapor altyapısı.", "Hazır"],
    ]


def build_pdf(output: Path = OUTPUT) -> Path:
    global _TABLE_STYLES
    font = register_font()
    style = styles(font)
    _TABLE_STYLES = style
    output.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M")
    document = SimpleDocTemplate(
        str(output), pagesize=PAGE, leftMargin=17 * mm, rightMargin=17 * mm,
        topMargin=17 * mm, bottomMargin=16 * mm,
        title="NetOps 1.52 Asistan ve Özellikler Raporu",
        author="NetOps",
    )
    story: list[object] = []

    story.append(rich("<font color='#4D8DFF'>NETOPS 1.52</font>", style["cover_title"]))
    story.append(p("Asistan, yeni özellikler ve yenilenen kullanıcı deneyimi", style["cover_subtitle"]))
    story.append(p(f"Rapor tarihi: {generated}  |  Kaynak çalışma sürümü: asistan beta.py", style["small"]))
    story.append(Spacer(1, 5 * mm))

    summary_rows = [
        [p("Genel durum", style["cell_muted"]), p("NetOps 1.52 kaynak arayüzü", style["cell"]), p("Doğrulama", style["cell_muted"]), p("48 test geçti", style["status"])],
        [p("Arayüz tabanı", style["cell_muted"]), p("PySide6 / Qt Widgets", style["cell"]), p("Çalıştırılan hedef", style["cell_muted"]), p("Sadece .py kaynak sürümü", style["cell"])],
        [p("Dil", style["cell_muted"]), p("Türkçe ve İngilizce", style["cell"]), p("Medya yenileme", style["cell_muted"]), p("1 saniyelik döngü", style["cell"])],
    ]
    summary = Table(summary_rows, colWidths=[28 * mm, 55 * mm, 30 * mm, 54 * mm], hAlign="LEFT")
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary)
    story.append(Spacer(1, 7 * mm))
    story.append(rich("<b>Bu belge neyi anlatıyor?</b>", style["h2"]))
    story.append(p("Bu rapor, NetOps asistanının mevcut yeteneklerini, 1.52 sürümünde yenilenen arayüz davranışlarını ve son doğrulama durumunu tek yerde toplar. Rapor, EXE paketini değil, güncel Python kaynak çalışma sürümünü esas alır.", style["body"]))

    highlight_rows = [
        [rich("<b>Sohbet deneyimi</b><br/><font color='#9EADCA'>WhatsApp benzeri sağ-sol mesaj baloncukları, asenkron yanıt ve gerçek yazıyor göstergesi.</font>", style["cell"]), rich("<b>Now Playing</b><br/><font color='#9EADCA'>Daire albüm kapağı, dokununca açılan kontroller, gerçek ses değeri ve canlı süre.</font>", style["cell"])],
        [rich("<b>Yerel yetenekler</b><br/><font color='#9EADCA'>Sistem, medya, cihaz, yardım ve Recovery Mesh skill alanları.</font>", style["cell"]), rich("<b>Güvenli kaynak akışı</b><br/><font color='#9EADCA'>Test edilmiş kaynak sürümü, ayar otomatik kaydı ve callback tabanlı cihaz işlemleri.</font>", style["cell"])],
    ]
    highlights = Table(highlight_rows, colWidths=[86 * mm, 86 * mm], hAlign="LEFT")
    highlights.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(highlights)

    story.append(PageBreak())
    story.append(p("Asistanın mevcut yetenekleri", style["h1"]))
    story.append(p("NetOps yalnızca bir sohbet kutusu değildir; yerel sistem bilgisi, medya, cihaz, otomasyon ve bakım yüzeylerini tek arayüzde birleştiren bir masaüstü asistanıdır.", style["body"]))
    rows = feature_rows()
    converted_rows = [[p(item, style["cell"]) for item in row] for row in rows]
    feature_table = Table(converted_rows, colWidths=[34 * mm, 108 * mm, 28 * mm], repeatRows=1, hAlign="LEFT")
    feature_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (2, 1), (2, -1), GREEN),
    ]))
    story.append(feature_table)
    story.append(Spacer(1, 7 * mm))
    story.append(p("Yerleşik skill alanları", style["h2"]))
    skill_rows = [
        ["Skill", "Ne yapar?"],
        ["Sistem", "CPU, RAM, disk ve pil durumunu okur."],
        ["Medya", "Şu an çalan medya bilgisini okur."],
        ["Cihazlar", "Bağlı NetOps cihazlarını listeler."],
        ["Komutlar", "Kullanılabilir yerleşik komutları açıklar."],
        ["Recovery Mesh", "Hataları teşhis eder ve onay gerektiren geri dönüş planı çıkarır."],
    ]
    story.append(table(skill_rows, [38 * mm, 132 * mm]))

    story.append(PageBreak())
    story.append(p("1.52 sürümünde yenilenen özellikler", style["h1"]))
    updates = [
        ("Sohbet alanı", "Mesajlar artık kullanıcı için sağda, NetOps için solda baloncuk olarak görünür. Yanıt hazırlanırken yerel GIF tabanlı üç nokta göstergesi çıkar; arayüz yanıt beklerken donmaz."),
        ("Composer", "Alt yazma alanı koyu, yuvarlatılmış bir kapsüle dönüştürüldü. Soldaki + düğmesi yeni sohbet açar; yazma alanı daha geniştir; gönder düğmesi ikonlu ve daha belirgindir. Enter ile gönderme korunur."),
        ("Hero alanı", "Mevcut üçgen logo korunur; yalnızca logonun siyah arka planı şeffaflaştırılır. Alt yazılar kaldırılır ve tek büyük başlık bırakılır: Sana nasıl yardımcı olabilirim?"),
        ("Now Playing dairesi", "Sohbet açıldığında yalnızca albüm kapağı daire olarak görünür. Kapağa dokununca kart genişler; kontroller, süre, ses kaydırıcısı, ses yüzdesi ve oynatma düğmeleri gelir. Fare kartın dışına çıkınca tekrar daireye döner."),
        ("Gerçek medya değeri", "Ses seviyesi sabit bir başlangıç değeriyle gösterilmez; medya backend'inden volume_get ile okunur ve % değer etiketi güncellenir. Parça, sanatçı, albüm, platform, kapak ve süre bilgisi canlı yenilenir."),
        ("İkon sistemi", "Windows stok ikonları yerine projeye gömülü, harici bağlantı gerektirmeyen Lucide tarzı SVG ikon paketi kullanılır."),
        ("Dil ve ayarlar", "Türkçe ve İngilizce arayüz metinleri yeniden çevrilebilir. Ayar değişiklikleri otomatik kaydedilir; tema, güvenlik, güncelleme ve açılış tercihleri ayrı sekmelerde tutulur."),
    ]
    update_rows = [[p("Yenilenen alan", style["cell"]), p("Yeni davranış", style["cell"])]]
    update_rows.extend([p(title, style["cell"]), p(description, style["cell"])] for title, description in updates)
    update_table = Table(update_rows, colWidths=[37 * mm, 133 * mm], repeatRows=1, hAlign="LEFT")
    update_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(update_table)

    story.append(PageBreak())
    story.append(p("Teknik yapı ve doğrulama", style["h1"]))
    technical_rows = [
        ["Katman", "Açıklama"],
        ["Başlatma", "asistan beta.py, NETOPS_QT_UI=1 ve NETOPS_LEGACY_UI=0 ile güncel Qt arayüzünü başlatır."],
        ["Arayüz", "netops_qt_shell.py; PySide6 Qt Widgets, yerel QSS tema, animasyonlar ve sayfa yönlendirmesi."],
        ["Backend", "netops_qt_backend.py; sistem, cihaz, medya, sohbet, ayar, Remote ve bildirim callback'lerini tek sözleşmede toplar."],
        ["Medya", "neto_now_playing.py; Windows medya oturumu, canlı zaman çizgisi, kapak ve medya kontrol köprüsü."],
        ["Skill keşfi", "neto_skill_loader.py; proje ve kullanıcı dizinlerindeki SKILL.md dosyalarını okur, seçer ve sınırlı bağlam üretir."],
        ["İkonlar", "netops_icon_pack.py; SVG ikonları yerel ve önbellekli olarak üretir, internet bağımlılığı eklemez."],
        ["Rapor", "neto_pdf_report.py ve bu özellik raporu; proje envanterini ve doğrulama durumunu belgelemek için kullanılır."],
    ]
    story.append(table(technical_rows, [34 * mm, 136 * mm]))
    story.append(Spacer(1, 7 * mm))
    story.append(p("Son doğrulama", style["h2"]))
    validation_rows = [
        ["Kontrol", "Sonuç"],
        ["Qt arayüz testleri", "48 test geçti"],
        ["Python derleme kontrolü", "Başarılı"],
        ["Kaynak çalışma sürümü", "NetOps 1.52 / asistan beta.py"],
        ["EXE kullanımı", "Bu güncellemede kullanılmadı"],
    ]
    story.append(table(validation_rows, [58 * mm, 112 * mm]))
    story.append(Spacer(1, 7 * mm))
    story.append(p("Bilgi sınırları", style["h2"]))
    story.append(p("Sohbet yanıtlarının kalitesi, projede bağlı olan yerel AI/sohbet motoruna göre değişir. Remote ve cihaz işlemleri, bağlantı ve callback durumuna bağlıdır; bağlantı yoksa işlem gönderilmez. Now Playing bilgisi de işletim sisteminin medya oturumuna ve sağlayıcının sunduğu gerçek zamanlı verilere bağlıdır.", style["body"]))
    story.append(p("Bu rapor bir kullanım ve durum özeti olarak hazırlanmıştır; işletim sistemi projesini değil, masaüstü NetOps uygulamasının güncel kaynak sürümünü kapsar.", style["small"]))

    def paint_page(canvas, _document) -> None:
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.8)
        canvas.line(17 * mm, PAGE[1] - 12 * mm, PAGE[0] - 17 * mm, PAGE[1] - 12 * mm)
        canvas.setFont(font, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(17 * mm, 8 * mm, "NetOps 1.52 - Asistan ve özellik raporu")
        canvas.drawRightString(PAGE[0] - 17 * mm, 8 * mm, f"Sayfa {canvas.getPageNumber()}")
        canvas.restoreState()

    document.build(story, onFirstPage=paint_page, onLaterPages=paint_page)
    return output


if __name__ == "__main__":
    print(build_pdf())

