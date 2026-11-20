"""التحليل الجماعي: رفع ملف CSV ← تحقق ← تنظيف ← معالجة ← XGBoost ← SHAP ← نتائج."""
from __future__ import annotations

import io
import uuid
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ...config import settings
from ...db.database import get_db
from ...db.models import Prediction, Student, User
from ...ml.explain import explain_student, global_importance
from ...ml.features import FEATURE_ORDER, ID_COLUMN
from ...ml.predict import ModelNotTrainedError, is_model_available, predict_batch
from ...ml.preprocessing import DataValidationError, validate_batch_dataframe
from ...services.reporting import rows_to_csv_bytes
from ..deps import log_action, require_permission
from ...utils import utcnow

router = APIRouter(prefix="/api/batch", tags=["batch"])

# تخزين مؤقت لنتائج الدفعات داخل الذاكرة (تُمسح عند إعادة التشغيل)
_BATCH_CACHE: dict[str, dict] = {}
_MAX_CACHED_BATCHES = 20


def _ensure_model() -> None:
    if not is_model_available("xgboost"):
        raise HTTPException(
            status_code=503, detail="النموذج غير مدرَّب بعد. نفّذ: python -m app.ml.train"
        )


@router.get("/template")
def download_template(_: User = Depends(require_permission("batch:run"))):
    """تنزيل قالب CSV فارغ بالأعمدة المطلوبة."""
    header = ",".join([ID_COLUMN] + FEATURE_ORDER)
    example = (
        "STU20250001,21,2.10,2.30,72.5,45,3,2,64.0,2,58.0,18.0,1,9,0,"
        "male,rural,low,secondary,information_systems,no,yes"
    )
    content = f"{header}\n{example}\n".encode("utf-8-sig")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="batch_template.csv"'},
    )


@router.post("/analyze")
async def analyze_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("batch:run")),
    save_to_history: bool = Query(True),
):
    """تحليل ملف CSV يحتوي على عدة طلاب."""
    _ensure_model()

    # --- التحقق من الملف (الامتداد، النوع، الحجم)
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(settings.ALLOWED_UPLOAD_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="نوع الملف غير مسموح به. يُقبل ملف بصيغة CSV فقط.",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="الملف فارغ.")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"حجم الملف يتجاوز الحد المسموح ({settings.MAX_UPLOAD_MB} ميجابايت)."
        )
    if b"\x00" in raw[:4096]:
        raise HTTPException(status_code=400, detail="الملف يبدو ثنائيًا وليس ملف CSV نصيًا.")

    # --- القراءة
    df = None
    for encoding in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=encoding)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if df is None:
        raise HTTPException(status_code=400, detail="تعذّر قراءة الملف. تأكد أنه ملف CSV صحيح.")

    # --- التحقق والتنظيف
    try:
        cleaned, warnings = validate_batch_dataframe(df)
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # --- المعالجة والتنبؤ
    try:
        predictions = predict_batch(cleaned)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    merged = cleaned.merge(predictions, on=ID_COLUMN, how="left")
    counts = predictions["risk_level"].value_counts().to_dict()
    summary = {
        "total": int(len(predictions)),
        "low": int(counts.get("low", 0)),
        "medium": int(counts.get("medium", 0)),
        "high": int(counts.get("high", 0)),
        "at_risk": int((predictions["prediction"] == 1).sum()),
        "avg_probability": round(float(predictions["probability"].mean()), 4),
    }
    summary["at_risk_percentage"] = round(
        100.0 * summary["at_risk"] / summary["total"], 2
    ) if summary["total"] else 0.0

    # --- SHAP: الأهمية العامة + تفسير أعلى حالة خطورة
    shap_payload = {}
    try:
        shap_payload["global"] = global_importance(top_k=12)
        top_idx = int(predictions["probability"].idxmax())
        top_row = cleaned.loc[top_idx, FEATURE_ORDER].to_dict()
        shap_payload["top_case"] = {
            "student_id": str(predictions.loc[top_idx, ID_COLUMN]),
            "probability": float(predictions.loc[top_idx, "probability"]),
            **explain_student(top_row, top_k=10),
        }
    except Exception as exc:  # pragma: no cover
        shap_payload["error"] = f"تعذّر توليد تفسير SHAP: {exc}"

    # --- حفظ في السجل
    saved = 0
    if save_to_history:
        known = {
            s.student_id: s
            for s in db.query(Student)
            .filter(Student.student_id.in_(predictions[ID_COLUMN].tolist()))
            .all()
        }
        for _, row in predictions.iterrows():
            student = known.get(row[ID_COLUMN])
            db.add(
                Prediction(
                    student_pk=student.id if student else None,
                    student_id=str(row[ID_COLUMN]),
                    model_name="xgboost",
                    prediction=int(row["prediction"]),
                    probability=float(row["probability"]),
                    risk_level=str(row["risk_level"]),
                    source="batch",
                    created_by_id=user.id,
                )
            )
            if student is not None:
                student.last_probability = float(row["probability"])
                student.last_risk_level = str(row["risk_level"])
                student.last_predicted_at = utcnow()
            saved += 1
        db.commit()

    batch_id = uuid.uuid4().hex[:12]
    results = predictions.to_dict(orient="records")
    if len(_BATCH_CACHE) >= _MAX_CACHED_BATCHES:
        _BATCH_CACHE.pop(next(iter(_BATCH_CACHE)))
    _BATCH_CACHE[batch_id] = {
        "results": results,
        "created_at": utcnow().isoformat(timespec="seconds"),
        "file_name": filename,
        "owner": user.id,
    }

    log_action(
        db, user, "batch_analyze", "batch",
        f"file={filename} rows={summary['total']} high={summary['high']}",
    )

    return {
        "batch_id": batch_id,
        "file_name": filename,
        "warnings": warnings,
        "summary": summary,
        "results": results,
        "shap": shap_payload,
        "preview_columns": [ID_COLUMN, "prediction", "probability", "risk_level", "risk_level_ar"],
        "merged_sample": merged.head(5).to_dict(orient="records"),
    }


@router.get("/{batch_id}/export")
def export_batch(
    batch_id: str,
    user: User = Depends(require_permission("batch:run")),
):
    """تصدير نتائج التحليل الجماعي كملف CSV."""
    entry = _BATCH_CACHE.get(batch_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="لم يتم العثور على نتائج هذه الدفعة (قد تكون انتهت).")
    if entry["owner"] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية لتصدير هذه النتائج.")

    rows = [
        {
            "student_id": r["student_id"],
            "prediction": r["prediction"],
            "probability": r["probability"],
            "risk_level": r["risk_level"],
            "risk_level_ar": r["risk_level_ar"],
        }
        for r in entry["results"]
    ]
    content = rows_to_csv_bytes(
        rows, ["student_id", "prediction", "probability", "risk_level", "risk_level_ar"]
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="batch_{batch_id}.csv"'},
    )
