"""لوحة التحكم الرئيسية: المؤشرات والإحصاءات والرسوم."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Prediction, Student, User
from ...ml.features import VALUE_LABELS_AR
from ...ml.predict import is_model_available
from ..deps import require_permission
from ...utils import utcnow

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _round(value, digits: int = 2) -> float:
    return round(float(value or 0), digits)


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:view")),
):
    total = db.query(func.count(Student.id)).scalar() or 0

    level_rows = (
        db.query(Student.last_risk_level, func.count(Student.id))
        .group_by(Student.last_risk_level)
        .all()
    )
    levels = {(k or "unknown"): c for k, c in level_rows}
    low = levels.get("low", 0)
    medium = levels.get("medium", 0)
    high = levels.get("high", 0)
    unknown = levels.get("unknown", 0)
    evaluated = low + medium + high
    at_risk = medium + high

    avg_gpa = db.query(func.avg(Student.gpa)).scalar()
    avg_attendance = db.query(func.avg(Student.attendance_rate)).scalar()
    avg_lms = db.query(func.avg(Student.lms_logins_per_week)).scalar()
    avg_submission = db.query(func.avg(Student.assignment_submission_rate)).scalar()
    avg_session = db.query(func.avg(Student.avg_session_minutes)).scalar()
    low_attendance = db.query(func.count(Student.id)).filter(Student.attendance_rate < 75).scalar()
    low_gpa = db.query(func.count(Student.id)).filter(Student.gpa < 2.0).scalar()

    return {
        "total_students": int(total),
        "evaluated": int(evaluated),
        "not_evaluated": int(unknown),
        "low": int(low),
        "medium": int(medium),
        "high": int(high),
        "at_risk": int(at_risk),
        "at_risk_percentage": _round(100.0 * at_risk / evaluated, 2) if evaluated else 0.0,
        "avg_gpa": _round(avg_gpa, 2),
        "avg_attendance": _round(avg_attendance, 1),
        "avg_lms_logins": _round(avg_lms, 1),
        "avg_submission_rate": _round(avg_submission, 1),
        "avg_session_minutes": _round(avg_session, 1),
        "low_attendance_count": int(low_attendance or 0),
        "low_gpa_count": int(low_gpa or 0),
        "model_ready": is_model_available("xgboost"),
        "generated_at": utcnow().isoformat(timespec="seconds") + "Z",
    }


@router.get("/charts")
def charts(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:view")),
):
    """بيانات الرسوم البيانية التفاعلية."""
    # توزيع مستويات الخطورة
    risk_rows = (
        db.query(Student.last_risk_level, func.count(Student.id))
        .group_by(Student.last_risk_level)
        .all()
    )
    labels_ar = {"low": "منخفض", "medium": "متوسط", "high": "مرتفع", None: "لم يُقيَّم"}
    risk_distribution = [
        {"key": k or "unknown", "label": labels_ar.get(k, "لم يُقيَّم"), "count": int(c)}
        for k, c in risk_rows
    ]

    # حسب التخصص
    major_rows = (
        db.query(
            Student.major,
            func.count(Student.id),
            func.sum(case((Student.last_risk_level == "high", 1), else_=0)),
            func.avg(Student.gpa),
        )
        .group_by(Student.major)
        .all()
    )
    by_major = [
        {
            "key": m,
            "label": VALUE_LABELS_AR.get(m, m),
            "count": int(c),
            "high": int(h or 0),
            "avg_gpa": _round(g, 2),
        }
        for m, c, h, g in major_rows
    ]

    # حسب السنة الدراسية
    year_rows = (
        db.query(
            Student.study_year,
            func.count(Student.id),
            func.sum(case((Student.last_risk_level == "high", 1), else_=0)),
        )
        .group_by(Student.study_year)
        .order_by(Student.study_year)
        .all()
    )
    by_year = [
        {"label": f"السنة {y}", "count": int(c), "high": int(h or 0)} for y, c, h in year_rows
    ]

    # توزيع المعدل التراكمي
    gpa_buckets = [(0, 1), (1, 2), (2, 2.5), (2.5, 3), (3, 3.5), (3.5, 4.01)]
    gpa_distribution = []
    for low, high in gpa_buckets:
        count = (
            db.query(func.count(Student.id))
            .filter(Student.gpa >= low, Student.gpa < high)
            .scalar()
        )
        gpa_distribution.append({"label": f"{low} - {min(high, 4)}", "count": int(count or 0)})

    # توزيع الحضور
    att_buckets = [(0, 50), (50, 65), (65, 75), (75, 85), (85, 95), (95, 100.01)]
    attendance_distribution = []
    for low, high in att_buckets:
        count = (
            db.query(func.count(Student.id))
            .filter(Student.attendance_rate >= low, Student.attendance_rate < high)
            .scalar()
        )
        attendance_distribution.append(
            {"label": f"{low}% - {min(int(high), 100)}%", "count": int(count or 0)}
        )

    # التفاعل الإلكتروني
    engagement_levels = [
        {"label": "ضعيف (أقل من 3)", "count": int(db.query(func.count(Student.id)).filter(Student.lms_logins_per_week < 3).scalar() or 0)},
        {"label": "متوسط (3 - 7)", "count": int(db.query(func.count(Student.id)).filter(Student.lms_logins_per_week >= 3, Student.lms_logins_per_week < 8).scalar() or 0)},
        {"label": "مرتفع (8 فأكثر)", "count": int(db.query(func.count(Student.id)).filter(Student.lms_logins_per_week >= 8).scalar() or 0)},
    ]

    # نشاط التنبؤات آخر 14 يومًا
    since = utcnow() - timedelta(days=14)
    activity_rows = (
        db.query(func.date(Prediction.created_at), func.count(Prediction.id))
        .filter(Prediction.created_at >= since)
        .group_by(func.date(Prediction.created_at))
        .all()
    )
    activity = [{"date": str(d), "count": int(c)} for d, c in activity_rows]

    return {
        "risk_distribution": risk_distribution,
        "by_major": by_major,
        "by_year": by_year,
        "gpa_distribution": gpa_distribution,
        "attendance_distribution": attendance_distribution,
        "engagement_levels": engagement_levels,
        "prediction_activity": activity,
    }


@router.get("/high-risk")
def high_risk_students(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:view")),
    limit: int = 10,
):
    rows = (
        db.query(Student)
        .filter(Student.last_risk_level == "high")
        .order_by(Student.last_probability.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "student_id": s.student_id,
            "full_name": s.full_name,
            "major": VALUE_LABELS_AR.get(s.major, s.major),
            "gpa": s.gpa,
            "attendance_rate": s.attendance_rate,
            "probability": s.last_probability,
            "risk_level": s.last_risk_level,
        }
        for s in rows
    ]
