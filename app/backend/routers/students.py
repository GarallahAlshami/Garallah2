"""إدارة الطلاب: إضافة، تعديل، حذف، بحث، عرض الملف والسجل الأكاديمي."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Prediction, Student, User
from ...ml.features import (
    CATEGORICAL_VALUES,
    FEATURE_GROUPS_AR,
    FEATURE_LABELS_AR,
    FEATURE_ORDER,
    NUMERIC_BOUNDS,
    VALUE_LABELS_AR,
)
from ...schemas import StudentCreate, StudentOut, StudentPage, StudentUpdate
from ..deps import log_action, require_permission
from ...utils import utcnow

router = APIRouter(prefix="/api/students", tags=["students"])


def student_features(student: Student) -> dict:
    """استخراج قاموس الخصائص المطلوبة للنموذج من كائن الطالب."""
    return {field: getattr(student, field) for field in FEATURE_ORDER}


@router.get("/schema")
def get_schema(_: User = Depends(require_permission("students:view"))):
    """مخطط حقول الطالب — تستخدمه الواجهة لبناء النماذج ديناميكيًا."""
    return {
        "groups": FEATURE_GROUPS_AR,
        "labels": FEATURE_LABELS_AR,
        "categories": CATEGORICAL_VALUES,
        "value_labels": VALUE_LABELS_AR,
        "bounds": {k: list(v) for k, v in NUMERIC_BOUNDS.items()},
    }


@router.get("", response_model=StudentPage)
def list_students(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("students:view")),
    search: str = Query("", max_length=120),
    risk_level: str = Query("", pattern="^(low|medium|high|)$"),
    major: str = Query("", max_length=48),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = Query("student_id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
):
    query = db.query(Student)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Student.student_id.ilike(pattern), Student.full_name.ilike(pattern)))
    if risk_level:
        query = query.filter(Student.last_risk_level == risk_level)
    if major:
        query = query.filter(Student.major == major)

    allowed_sorts = {
        "student_id": Student.student_id,
        "full_name": Student.full_name,
        "gpa": Student.gpa,
        "attendance_rate": Student.attendance_rate,
        "last_probability": Student.last_probability,
        "study_year": Student.study_year,
    }
    column = allowed_sorts.get(sort_by, Student.student_id)
    query = query.order_by(column.desc() if sort_dir == "desc" else column.asc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return StudentPage(
        items=[StudentOut.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=StudentOut, status_code=201)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("students:manage")),
):
    exists = db.query(Student).filter(Student.student_id == payload.student_id).first()
    if exists:
        raise HTTPException(status_code=409, detail="رقم الطالب مستخدم بالفعل.")
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    log_action(db, user, "student_create", "students", student.student_id)
    return StudentOut.model_validate(student)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("students:view")),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")
    return StudentOut.model_validate(student)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: str,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("students:manage")),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث.")
    for key, value in updates.items():
        setattr(student, key, value)
    student.updated_at = utcnow()
    db.commit()
    db.refresh(student)
    log_action(db, user, "student_update", "students", f"{student_id}: {list(updates)}")
    return StudentOut.model_validate(student)


@router.delete("/{student_id}")
def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("students:manage")),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")
    db.delete(student)
    db.commit()
    log_action(db, user, "student_delete", "students", student_id, level="warning")
    return {"detail": "تم حذف الطالب بنجاح."}


@router.get("/{student_id}/history")
def student_history(
    student_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("students:view")),
    limit: int = Query(50, ge=1, le=500),
):
    """السجل الأكاديمي/سجل التنبؤات السابقة للطالب."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")

    rows = (
        db.query(Prediction)
        .filter(Prediction.student_id == student_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "student_id": student_id,
        "academic_record": {
            "gpa": student.gpa,
            "previous_gpa": student.previous_gpa,
            "gpa_change": round(student.gpa - student.previous_gpa, 2),
            "credits_completed": student.credits_completed,
            "failed_courses": student.failed_courses,
            "study_year": student.study_year,
            "admission_score": student.admission_score,
            "attendance_rate": student.attendance_rate,
            "assignment_submission_rate": student.assignment_submission_rate,
            "lms_logins_per_week": student.lms_logins_per_week,
        },
        "predictions": [
            {
                "id": p.id,
                "model_name": p.model_name,
                "prediction": p.prediction,
                "probability": p.probability,
                "risk_level": p.risk_level,
                "source": p.source,
                "created_at": p.created_at,
            }
            for p in rows
        ],
    }


@router.get("/meta/majors")
def majors(db: Session = Depends(get_db), _: User = Depends(require_permission("students:view"))):
    rows = db.query(Student.major, func.count(Student.id)).group_by(Student.major).all()
    return [
        {"value": m, "label": VALUE_LABELS_AR.get(m, m), "count": c}
        for m, c in rows
    ]
