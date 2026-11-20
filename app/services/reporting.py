"""مركز التقارير: توليد ملفات CSV و PDF باللغة العربية."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import settings
from ..ml.features import VALUE_LABELS_AR

def _pct(value: float | None) -> str:
    """نسبة مئوية بخانة عشرية واحدة، دون إظهار 100% لاحتمالية أقل من الواحد الصحيح."""
    raw = (value or 0) * 100
    if 0 < raw < 100 and round(raw, 1) >= 100:
        return "99.9%"
    if raw > 0 and round(raw, 1) <= 0:
        return "0.1%"
    return f"{raw:.1f}%"

FONT_NAME = "ArabicFont"
_FONT_REGISTERED = False


# ---------------------------------------------------------------- أدوات عربية
def ar(text) -> str:
    """تشكيل النص العربي (Reshape + Bidi) ليُعرض بشكل صحيح داخل PDF."""
    text = "" if text is None else str(text)
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:  # pragma: no cover
        return text


def _register_font() -> bool:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return True
    font_path = settings.ASSETS_DIR / "fonts" / "Arabic-Regular.ttf"
    if not font_path.exists():
        return False
    try:
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
        _FONT_REGISTERED = True
        return True
    except Exception:  # pragma: no cover
        return False


def pdf_available() -> bool:
    return _register_font()


# --------------------------------------------------------------------- CSV
def rows_to_csv_bytes(rows: list[dict], headers: list[str] | None = None) -> bytes:
    """تحويل قائمة قواميس إلى ملف CSV مشفّر UTF-8 BOM (ليفتح صحيحًا في Excel)."""
    headers = headers or (list(rows[0].keys()) if rows else [])
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


# --------------------------------------------------------------------- PDF
def _styles():
    base = getSampleStyleSheet()
    font = FONT_NAME if _register_font() else "Helvetica"
    return {
        "title": ParagraphStyle(
            "ar_title", parent=base["Title"], fontName=font, fontSize=17, leading=24,
            alignment=TA_CENTER, textColor=colors.HexColor("#1f3a5f"),
        ),
        "h2": ParagraphStyle(
            "ar_h2", parent=base["Heading2"], fontName=font, fontSize=13, leading=20,
            alignment=TA_RIGHT, textColor=colors.HexColor("#2c5f8a"),
        ),
        "body": ParagraphStyle(
            "ar_body", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=18,
            alignment=TA_RIGHT,
        ),
        "small": ParagraphStyle(
            "ar_small", parent=base["BodyText"], fontName=font, fontSize=8.5, leading=13,
            alignment=TA_CENTER, textColor=colors.HexColor("#666666"),
        ),
        "font": font,
    }


def _table(data: list[list[str]], col_widths=None, font="Helvetica") -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5f8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d6e2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _document(path: Path, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="Early Warning System",
    )


def _header(story: list, styles: dict, title: str, subtitle: str = "") -> None:
    story.append(Paragraph(ar(settings.APP_NAME), styles["title"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(ar(title), styles["h2"]))
    if subtitle:
        story.append(Paragraph(ar(subtitle), styles["body"]))
    story.append(
        Paragraph(
            ar(f"تاريخ إنشاء التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), styles["small"]
        )
    )
    story.append(Spacer(1, 10))


def _footer_note(story: list, styles: dict) -> None:
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            ar(
                "ملاحظة: هذا التقرير صادر عن نظام إنذار مبكر ذكي (نموذج أكاديمي أولي). "
                "نتائج النموذج مساندة لقرار المرشد الأكاديمي ولا تُغني عن التقييم البشري."
            ),
            styles["small"],
        )
    )


def student_report_pdf(
    path: Path,
    student: dict,
    prediction: dict,
    factors: list[dict],
    recommendations: list[dict],
    plot_path: Path | None = None,
) -> Path:
    """تقرير طالب واحد."""
    styles = _styles()
    doc = _document(path, "تقرير طالب")
    story: list = []
    _header(story, styles, "تقرير حالة طالب", f"رقم الطالب: {student.get('student_id', '-')}")

    info = [
        [ar("القيمة"), ar("البيان")],
        [ar(student.get("full_name", "-")), ar("اسم الطالب")],
        [ar(VALUE_LABELS_AR.get(str(student.get("major", "-")), str(student.get("major", "-")))), ar("التخصص")],
        [ar(str(student.get("study_year", "-"))), ar("السنة الدراسية")],
        [ar(f"{student.get('gpa', 0):.2f}"), ar("المعدل التراكمي")],
        [ar(f"{student.get('attendance_rate', 0):.1f}%"), ar("نسبة الحضور")],
        [ar(str(student.get("lms_logins_per_week", 0))), ar("الدخول الأسبوعي للمنصة")],
        [ar(str(student.get("failed_courses", 0))), ar("المقررات المتعثرة")],
    ]
    story.append(_table(info, [95 * mm, 75 * mm], styles["font"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(ar("نتيجة التنبؤ"), styles["h2"]))
    pred = [
        [ar("القيمة"), ar("المؤشر")],
        [ar(prediction.get("prediction_label", "-")), ar("التنبؤ")],
        [ar(_pct(prediction.get("probability", 0))), ar("احتمال التسرب")],
        [ar(prediction.get("risk_level_ar", "-")), ar("مستوى الخطورة")],
        [ar(prediction.get("model", "xgboost")), ar("النموذج المستخدم")],
    ]
    story.append(_table(pred, [95 * mm, 75 * mm], styles["font"]))
    story.append(Spacer(1, 12))

    if factors:
        story.append(Paragraph(ar("أهم العوامل المؤثرة في القرار (SHAP)"), styles["h2"]))
        rows = [[ar("الأثر"), ar("قيمة SHAP"), ar("العامل")]]
        for f in factors[:10]:
            rows.append(
                [
                    ar("يرفع الخطر" if f.get("direction") == "increase" else "يخفض الخطر"),
                    ar(f"{f.get('shap_value', 0):+.3f}"),
                    ar(f.get("feature_ar", f.get("feature", "-"))),
                ]
            )
        story.append(_table(rows, [40 * mm, 35 * mm, 95 * mm], styles["font"]))
        story.append(Spacer(1, 12))

    if plot_path and Path(plot_path).exists():
        story.append(Paragraph(ar("الرسم التفسيري"), styles["h2"]))
        story.append(Image(str(plot_path), width=168 * mm, height=100 * mm, kind="proportional"))
        story.append(Spacer(1, 10))

    if recommendations:
        story.append(Paragraph(ar("التوصيات الإرشادية"), styles["h2"]))
        for i, rec in enumerate(recommendations, start=1):
            story.append(
                Paragraph(ar(f"{i}. {rec['title_ar']} — {rec.get('trigger_ar', '')}"), styles["body"])
            )
            story.append(Paragraph(ar(f"   {rec['action_ar']}"), styles["body"]))
            story.append(Spacer(1, 4))

    _footer_note(story, styles)
    doc.build(story)
    return path


def high_risk_report_pdf(path: Path, rows: list[dict], summary: dict) -> Path:
    """تقرير الطلاب مرتفعي الخطورة."""
    styles = _styles()
    doc = _document(path, "تقرير الطلاب مرتفعي الخطورة")
    story: list = []
    _header(story, styles, "تقرير الطلاب مرتفعي الخطورة", f"عدد الحالات: {len(rows)}")

    stats = [
        [ar("القيمة"), ar("المؤشر")],
        [ar(str(summary.get("total_students", 0))), ar("إجمالي الطلاب")],
        [ar(str(summary.get("high", 0))), ar("مرتفعو الخطورة")],
        [ar(str(summary.get("medium", 0))), ar("متوسطو الخطورة")],
        [ar(str(summary.get("low", 0))), ar("منخفضو الخطورة")],
        [ar(f"{summary.get('at_risk_percentage', 0):.1f}%"), ar("نسبة المعرضين للتسرب")],
    ]
    story.append(_table(stats, [95 * mm, 75 * mm], styles["font"]))
    story.append(Spacer(1, 12))

    data = [[ar("الحضور"), ar("المعدل"), ar("الاحتمال"), ar("مستوى الخطر"), ar("رقم الطالب")]]
    for r in rows[:300]:
        data.append(
            [
                ar(f"{r.get('attendance_rate', 0):.0f}%"),
                ar(f"{r.get('gpa', 0):.2f}"),
                ar(_pct(r.get("probability"))),
                ar(r.get("risk_level_ar", "-")),
                ar(r.get("student_id", "-")),
            ]
        )
    story.append(_table(data, [25 * mm, 25 * mm, 30 * mm, 35 * mm, 55 * mm], styles["font"]))
    _footer_note(story, styles)
    doc.build(story)
    return path


def statistics_report_pdf(
    path: Path, summary: dict, distributions: dict, model_comparison: dict,
    importance_plot: Path | None = None,
) -> Path:
    """تقرير إحصائي شامل."""
    styles = _styles()
    doc = _document(path, "تقرير إحصائي شامل")
    story: list = []
    _header(story, styles, "التقرير الإحصائي الشامل", "ملخص أداء النظام ومؤشرات الطلاب")

    stats = [
        [ar("القيمة"), ar("المؤشر")],
        [ar(str(summary.get("total_students", 0))), ar("إجمالي عدد الطلاب")],
        [ar(str(summary.get("low", 0))), ar("طلاب منخفضو الخطورة")],
        [ar(str(summary.get("medium", 0))), ar("طلاب متوسطو الخطورة")],
        [ar(str(summary.get("high", 0))), ar("طلاب مرتفعو الخطورة")],
        [ar(f"{summary.get('at_risk_percentage', 0):.1f}%"), ar("نسبة الطلاب المعرضين للتسرب")],
        [ar(f"{summary.get('avg_gpa', 0):.2f}"), ar("متوسط المعدل التراكمي")],
        [ar(f"{summary.get('avg_attendance', 0):.1f}%"), ar("متوسط نسبة الحضور")],
        [ar(f"{summary.get('avg_lms_logins', 0):.1f}"), ar("متوسط الدخول الأسبوعي للمنصة")],
    ]
    story.append(_table(stats, [95 * mm, 75 * mm], styles["font"]))
    story.append(Spacer(1, 12))

    if distributions.get("by_major"):
        story.append(Paragraph(ar("توزيع الطلاب حسب التخصص"), styles["h2"]))
        rows = [[ar("مرتفعو الخطورة"), ar("العدد"), ar("التخصص")]]
        for item in distributions["by_major"]:
            rows.append([ar(str(item["high"])), ar(str(item["count"])), ar(item["label"])])
        story.append(_table(rows, [45 * mm, 40 * mm, 85 * mm], styles["font"]))
        story.append(Spacer(1, 12))

    story.append(PageBreak())
    story.append(Paragraph(ar("مقارنة أداء النماذج — النتائج الموثقة في التقرير"), styles["h2"]))
    documented = model_comparison.get("documented", {})
    rows = [[ar("AUC-ROC"), ar("F1"), ar("Recall"), ar("Precision"), ar("Accuracy"), ar("النموذج")]]
    for key, label in (
        ("logistic_regression", "الانحدار اللوجستي"),
        ("xgboost", "XGBoost"),
    ):
        m = documented.get(key, {})
        rows.append(
            [
                ar(f"{m.get('auc_roc', 0):.2f}"),
                ar(f"{m.get('f1', 0):.2f}"),
                ar(f"{m.get('recall', 0):.2f}"),
                ar(f"{m.get('precision', 0):.2f}"),
                ar(f"{m.get('accuracy', 0):.2f}"),
                ar(label),
            ]
        )
    story.append(_table(rows, [25 * mm, 22 * mm, 25 * mm, 27 * mm, 27 * mm, 44 * mm], styles["font"]))
    story.append(Spacer(1, 10))

    if importance_plot and Path(importance_plot).exists():
        story.append(Paragraph(ar("الأهمية العامة للخصائص (SHAP)"), styles["h2"]))
        story.append(Image(str(importance_plot), width=168 * mm, height=110 * mm, kind="proportional"))

    _footer_note(story, styles)
    doc.build(story)
    return path
