"""التنبؤ الفردي بخطر التسرب + التفسير + التوصيات."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Prediction, RiskFactor, Student, User
from ...ml.explain import explain_student
from ...ml.features import FEATURE_ORDER
from ...ml.predict import ModelNotTrainedError, is_model_available, predict_one
from ...schemas import StudentBase
from ...services.recommendations import build_recommendations
from ..deps import log_action, require_permission
from ...utils import utcnow

router = APIRouter(prefix="/api/predict", tags=["predict"])


def _ensure_model() -> None:
    if not is_model_available("xgboost"):
        raise HTTPException(
            status_code=503,
            detail="النموذج غير مدرَّب بعد. نفّذ الأمر: python -m app.ml.train",
        )


def _persist(
    db: Session, user: User, student: Student | None, student_id: str, result: dict,
    factors: list[dict], source: str = "single",
) -> Prediction:
    record = Prediction(
        student_pk=student.id if student else None,
        student_id=student_id,
        model_name=result["model"],
        prediction=result["prediction"],
        probability=result["probability"],
        risk_level=result["risk_level"],
        source=source,
        created_by_id=user.id,
    )
    db.add(record)
    db.flush()
    for rank, f in enumerate(factors[:10], start=1):
        db.add(
            RiskFactor(
                prediction_id=record.id,
                feature=f["feature"],
                feature_ar=f["feature_ar"],
                shap_value=f["shap_value"],
                direction=f["direction"],
                rank=rank,
            )
        )
    if student is not None:
        student.last_probability = result["probability"]
        student.last_risk_level = result["risk_level"]
        student.last_predicted_at = utcnow()
    db.commit()
    db.refresh(record)
    return record


@router.post("/student/{student_id}")
def predict_registered_student(
    student_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("predict:run")),
    explain: bool = Query(True),
    top_k: int = Query(10, ge=3, le=25),
):
    """تنبؤ لطالب مسجّل في قاعدة البيانات مع تفسير SHAP والتوصيات."""
    _ensure_model()
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")

    features = {field: getattr(student, field) for field in FEATURE_ORDER}
    try:
        result = predict_one(features)
        explanation = explain_student(features, top_k=top_k) if explain else {"top_factors": []}
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record = _persist(db, user, student, student_id, result, explanation.get("top_factors", []))
    recommendations = build_recommendations(db, features, result["risk_level"])
    log_action(db, user, "predict_single", "predictions", f"{student_id} -> {result['risk_level']}")

    return {
        "student_id": student_id,
        "student_name": student.full_name,
        "prediction": result,
        "explanation": explanation,
        "recommendations": recommendations,
        "prediction_id": record.id,
        "created_at": record.created_at,
    }


@router.post("/manual")
def predict_manual(
    payload: StudentBase,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("predict:run")),
    top_k: int = Query(10, ge=3, le=25),
):
    """تنبؤ سريع لبيانات مُدخلة يدويًا دون حفظ الطالب."""
    _ensure_model()
    features = {field: getattr(payload, field) for field in FEATURE_ORDER}
    try:
        result = predict_one(features)
        explanation = explain_student(features, top_k=top_k)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    recommendations = build_recommendations(db, features, result["risk_level"])
    log_action(db, user, "predict_manual", "predictions", f"risk={result['risk_level']}")
    return {
        "student_id": "-",
        "prediction": result,
        "explanation": explanation,
        "recommendations": recommendations,
    }


@router.post("/all")
def predict_all_students(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("predict:run")),
    only_missing: bool = Query(False, description="تقييم الطلاب غير المقيّمين فقط"),
):
    """تشغيل التنبؤ على جميع الطلاب المسجلين وتحديث مستويات الخطورة."""
    _ensure_model()
    import pandas as pd

    from ...ml.predict import predict_batch

    query = db.query(Student)
    if only_missing:
        query = query.filter(Student.last_risk_level.is_(None))
    students = query.all()
    if not students:
        return {"processed": 0, "detail": "لا يوجد طلاب لتقييمهم."}

    frame = pd.DataFrame(
        [
            {"student_id": s.student_id, **{f: getattr(s, f) for f in FEATURE_ORDER}}
            for s in students
        ]
    )
    results = predict_batch(frame).set_index("student_id")
    now = utcnow()
    counts = {"low": 0, "medium": 0, "high": 0}
    for student in students:
        row = results.loc[student.student_id]
        student.last_probability = float(row["probability"])
        student.last_risk_level = str(row["risk_level"])
        student.last_predicted_at = now
        counts[student.last_risk_level] += 1
        db.add(
            Prediction(
                student_pk=student.id,
                student_id=student.student_id,
                model_name="xgboost",
                prediction=int(row["prediction"]),
                probability=float(row["probability"]),
                risk_level=str(row["risk_level"]),
                source="bulk",
                created_by_id=user.id,
            )
        )
    db.commit()
    log_action(db, user, "predict_all", "predictions", f"processed={len(students)}")
    return {"processed": len(students), "counts": counts}


@router.get("/history")
def prediction_history(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("predict:run")),
    limit: int = Query(50, ge=1, le=500),
):
    rows = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(limit).all()
    return [
        {
            "id": p.id,
            "student_id": p.student_id,
            "model_name": p.model_name,
            "prediction": p.prediction,
            "probability": p.probability,
            "risk_level": p.risk_level,
            "source": p.source,
            "created_at": p.created_at,
        }
        for p in rows
    ]
