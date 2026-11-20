"""مسارات الذكاء الاصطناعي القابل للتفسير (SHAP)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Student, User
from ...ml.explain import PLOTS_DIR, explain_student, global_importance, importance_png, waterfall_png
from ...ml.features import FEATURE_ORDER
from ...ml.predict import ModelNotTrainedError, is_model_available
from ..deps import require_permission

router = APIRouter(prefix="/api/explain", tags=["explain"])


def _ensure_model() -> None:
    if not is_model_available("xgboost"):
        raise HTTPException(
            status_code=503, detail="النموذج غير مدرَّب بعد. نفّذ: python -m app.ml.train"
        )


@router.get("/importance")
def feature_importance(
    _: User = Depends(require_permission("explain:view")),
    top_k: int = Query(15, ge=5, le=40),
):
    """الأهمية العامة للخصائص (SHAP Feature Importance / Bar Plot)."""
    _ensure_model()
    try:
        return global_importance(top_k=top_k)
    except (FileNotFoundError, ModelNotTrainedError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/importance/plot")
def feature_importance_plot(
    _: User = Depends(require_permission("explain:view")),
    top_k: int = Query(15, ge=5, le=40),
):
    _ensure_model()
    path = importance_png(PLOTS_DIR / f"importance_{top_k}.png", top_k=top_k)
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/student/{student_id}")
def explain_registered_student(
    student_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("explain:view")),
    top_k: int = Query(12, ge=3, le=30),
):
    """تفسير مفصّل لتنبؤ طالب: العوامل الرافعة والخافضة لمستوى الخطر."""
    _ensure_model()
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")

    features = {field: getattr(student, field) for field in FEATURE_ORDER}
    result = explain_student(features, top_k=top_k)
    result["student_id"] = student_id
    result["student_name"] = student.full_name
    result["narrative_ar"] = _narrative(result)
    return result


@router.get("/student/{student_id}/waterfall")
def student_waterfall(
    student_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("explain:view")),
    top_k: int = Query(12, ge=3, le=30),
):
    _ensure_model()
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الطالب.")
    features = {field: getattr(student, field) for field in FEATURE_ORDER}
    safe_name = "".join(c for c in student_id if c.isalnum() or c in "-_")
    path = waterfall_png(features, PLOTS_DIR / f"waterfall_{safe_name}.png", top_k=top_k)
    return FileResponse(path, media_type="image/png", filename=path.name)


def _narrative(result: dict) -> str:
    """صياغة شرح عربي مبسّط لسبب القرار."""
    up = result.get("increasing_risk", [])[:3]
    down = result.get("decreasing_risk", [])[:3]
    parts: list[str] = []
    if up:
        names = "، ".join(f["feature_ar"] for f in up)
        parts.append(f"رفعت العوامل التالية مستوى الخطر لدى الطالب: {names}.")
    if down:
        names = "، ".join(f["feature_ar"] for f in down)
        parts.append(f"في المقابل خفّضت العوامل التالية مستوى الخطر: {names}.")
    if not parts:
        parts.append("لم تُسجَّل عوامل ذات تأثير جوهري على قرار النموذج لهذا الطالب.")
    parts.append(
        "قيمة SHAP الموجبة تعني أن المتغير دفع النموذج نحو تصنيف الطالب كمعرّض للتسرب، "
        "والقيمة السالبة تعني أنه دفع النموذج في الاتجاه المعاكس."
    )
    return " ".join(parts)
