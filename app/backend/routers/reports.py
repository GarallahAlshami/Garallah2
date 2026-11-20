"""مركز التقارير: تقرير طالب، تقرير مرتفعي الخطورة، تقرير إحصائي شامل (CSV / PDF)."""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...config import settings
from ...db.database import get_db
from ...db.models import Report, Student, User
from ...ml.explain import PLOTS_DIR, explain_student, importance_png, waterfall_png
from ...ml.evaluate import comparison_payload
from ...ml.features import FEATURE_ORDER, VALUE_LABELS_AR
from ...ml.predict import is_model_available, predict_one, risk_label_ar
from ...services.recommendations import build_recommendations
from ...services.reporting import (
    high_risk_report_pdf,
    pdf_available,
    rows_to_csv_bytes,
    statistics_report_pdf,
    student_report_pdf,
)
from ..deps import log_action, require_permission

router = APIRouter(prefix="/api/reports", tags=["reports"])

_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _safe(name: str) -> str:
    return _SAFE.sub("", str(name))[:40] or "report"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _summary(db: Session) -> dict:
    total = db.query(func.count(Student.id)).scalar() or 0
    rows = (
        db.query(Student.last_risk_level, func.count(Student.id))
        .group_by(Student.last_risk_level)
        .all()
    )
    levels = {(k or "unknown"): int(c) for k, c in rows}
    low, medium, high = levels.get("low", 0), levels.get("medium", 0), levels.get("high", 0)
    evaluated = low + medium + high
    return {
        "total_students": int(total),
        "low": low,
        "medium": medium,
        "high": high,
        "at_risk_percentage": round(100.0 * (medium + high) / evaluated, 2) if evaluated else 0.0,
        "avg_gpa": round(float(db.query(func.avg(Student.gpa)).scalar() or 0), 2),
        "avg_attendance": round(float(db.query(func.avg(Student.attendance_rate)).scalar() or 0), 1),
        "avg_lms_logins": round(
            float(db.query(func.avg(Student.lms_logins_per_week)).scalar() or 0), 1
        ),
    }


def _record(db: Session, user: User, report_type: str, title: str, file_name: str, fmt: str) -> None:
    db.add(
        Report(
            report_type=report_type,
            title=title,
            file_name=file_name,
            file_format=fmt,
            created_by_id=user.id,
        )
    )
    db.commit()


@router.get("/capabilities")
def capabilities(_: User = Depends(require_permission("reports:view"))):
    return {"csv": True, "pdf": pdf_available(), "model_ready": is_model_available("xgboost")}


@router.get("/history")
def history(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
    limit: int = Query(30, ge=1, le=200),
):
    rows = db.query(Report).order_by(Report.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "title": r.title,
            "file_name": r.file_name,
            "file_format": r.file_format,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ---------------------------------------------------------------- تقرير طالب
@router.get("/student/{student_id}")
def student_report(
    student_id: str,
    fmt: str = Query("pdf", pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:create")),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")

    features = {f: getattr(student, f) for f in FEATURE_ORDER}
    if not is_model_available("xgboost"):
        raise HTTPException(status_code=503, detail="النموذج غير مدرَّب بعد.")

    prediction = predict_one(features)
    explanation = explain_student(features, top_k=10)
    recommendations = build_recommendations(db, features, prediction["risk_level"])

    student_dict = {
        "student_id": student.student_id,
        "full_name": student.full_name or "-",
        "major": VALUE_LABELS_AR.get(student.major, student.major),
        **features,
    }

    if fmt == "csv":
        rows = [
            {
                "student_id": student.student_id,
                "full_name": student.full_name,
                **features,
                "prediction": prediction["prediction"],
                "probability": prediction["probability"],
                "risk_level": prediction["risk_level"],
                "risk_level_ar": prediction["risk_level_ar"],
            }
        ]
        content = rows_to_csv_bytes(rows)
        name = f"student_{_safe(student_id)}_{_stamp()}.csv"
        _record(db, user, "student", f"تقرير الطالب {student_id}", name, "csv")
        log_action(db, user, "report_student_csv", "reports", student_id)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if not pdf_available():
        raise HTTPException(status_code=503, detail="تصدير PDF غير متاح (ملف الخط العربي مفقود).")

    plot = waterfall_png(features, PLOTS_DIR / f"report_{_safe(student_id)}.png", top_k=10)
    name = f"student_{_safe(student_id)}_{_stamp()}.pdf"
    path = settings.REPORTS_DIR / name
    student_report_pdf(
        path, student_dict, prediction, explanation["top_factors"], recommendations, plot
    )
    _record(db, user, "student", f"تقرير الطالب {student_id}", name, "pdf")
    log_action(db, user, "report_student_pdf", "reports", student_id)
    return FileResponse(path, media_type="application/pdf", filename=name)


# ------------------------------------------------------- تقرير مرتفعي الخطورة
@router.get("/high-risk")
def high_risk_report(
    fmt: str = Query("pdf", pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:create")),
):
    students = (
        db.query(Student)
        .filter(Student.last_risk_level == "high")
        .order_by(Student.last_probability.desc())
        .all()
    )
    if not students:
        raise HTTPException(
            status_code=404,
            detail="لا يوجد طلاب مصنّفون كمرتفعي الخطورة. شغّل التنبؤ الجماعي أولًا.",
        )

    rows = [
        {
            "student_id": s.student_id,
            "full_name": s.full_name,
            "major": VALUE_LABELS_AR.get(s.major, s.major),
            "study_year": s.study_year,
            "gpa": s.gpa,
            "attendance_rate": s.attendance_rate,
            "lms_logins_per_week": s.lms_logins_per_week,
            "failed_courses": s.failed_courses,
            "probability": s.last_probability,
            "risk_level": s.last_risk_level,
            "risk_level_ar": risk_label_ar(s.last_risk_level or ""),
        }
        for s in students
    ]

    if fmt == "csv":
        content = rows_to_csv_bytes(rows)
        name = f"high_risk_{_stamp()}.csv"
        _record(db, user, "high_risk", "تقرير الطلاب مرتفعي الخطورة", name, "csv")
        log_action(db, user, "report_high_risk_csv", "reports", f"count={len(rows)}")
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if not pdf_available():
        raise HTTPException(status_code=503, detail="تصدير PDF غير متاح (ملف الخط العربي مفقود).")

    name = f"high_risk_{_stamp()}.pdf"
    path = settings.REPORTS_DIR / name
    high_risk_report_pdf(path, rows, _summary(db))
    _record(db, user, "high_risk", "تقرير الطلاب مرتفعي الخطورة", name, "pdf")
    log_action(db, user, "report_high_risk_pdf", "reports", f"count={len(rows)}")
    return FileResponse(path, media_type="application/pdf", filename=name)


# ------------------------------------------------------- التقرير الإحصائي
@router.get("/statistics")
def statistics_report(
    fmt: str = Query("pdf", pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:create")),
):
    summary = _summary(db)
    major_rows = (
        db.query(Student.major, func.count(Student.id), func.avg(Student.gpa))
        .group_by(Student.major)
        .all()
    )
    by_major = []
    for major, count, avg_gpa in major_rows:
        high = (
            db.query(func.count(Student.id))
            .filter(Student.major == major, Student.last_risk_level == "high")
            .scalar()
        )
        by_major.append(
            {
                "key": major,
                "label": VALUE_LABELS_AR.get(major, major),
                "count": int(count),
                "avg_gpa": round(float(avg_gpa or 0), 2),
                "high": int(high or 0),
            }
        )

    if fmt == "csv":
        rows = [{"المؤشر": k, "القيمة": v} for k, v in summary.items()]
        rows += [
            {"المؤشر": f"التخصص: {m['label']} — العدد", "القيمة": m["count"]} for m in by_major
        ]
        rows += [
            {"المؤشر": f"التخصص: {m['label']} — مرتفعو الخطورة", "القيمة": m["high"]}
            for m in by_major
        ]
        content = rows_to_csv_bytes(rows, ["المؤشر", "القيمة"])
        name = f"statistics_{_stamp()}.csv"
        _record(db, user, "statistics", "التقرير الإحصائي الشامل", name, "csv")
        log_action(db, user, "report_statistics_csv", "reports")
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if not pdf_available():
        raise HTTPException(status_code=503, detail="تصدير PDF غير متاح (ملف الخط العربي مفقود).")

    plot = None
    if is_model_available("xgboost"):
        try:
            plot = importance_png(PLOTS_DIR / "importance_report.png", top_k=12)
        except Exception:  # pragma: no cover
            plot = None

    name = f"statistics_{_stamp()}.pdf"
    path = settings.REPORTS_DIR / name
    statistics_report_pdf(path, summary, {"by_major": by_major}, comparison_payload(), plot)
    _record(db, user, "statistics", "التقرير الإحصائي الشامل", name, "pdf")
    log_action(db, user, "report_statistics_pdf", "reports")
    return FileResponse(path, media_type="application/pdf", filename=name)


# -------------------------------------------------------- تصدير كل الطلاب
@router.get("/students/export")
def export_students(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:create")),
):
    students = db.query(Student).order_by(Student.student_id).all()
    rows = [
        {
            "student_id": s.student_id,
            "full_name": s.full_name,
            **{f: getattr(s, f) for f in FEATURE_ORDER},
            "probability": s.last_probability,
            "risk_level": s.last_risk_level,
        }
        for s in students
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="لا يوجد طلاب لتصديرهم.")
    content = rows_to_csv_bytes(rows)
    name = f"students_{_stamp()}.csv"
    _record(db, user, "students_export", "تصدير بيانات الطلاب", name, "csv")
    log_action(db, user, "report_students_export", "reports", f"count={len(rows)}")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
