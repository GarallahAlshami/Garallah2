"""خدمة التنبؤ: تحميل النموذج المدرَّب وإنتاج التنبؤ والاحتمال ومستوى الخطورة."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ..config import settings
from .features import FEATURE_ORDER, ID_COLUMN
from .preprocessing import prepare_features

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {}

MODEL_FILES = {
    "xgboost": settings.MODELS_DIR / "xgboost_pipeline.joblib",
    "logistic_regression": settings.MODELS_DIR / "logistic_regression_pipeline.joblib",
}

RISK_LABELS_AR = {"low": "منخفض", "medium": "متوسط", "high": "مرتفع"}


class ModelNotTrainedError(RuntimeError):
    """يُرفع عند محاولة التنبؤ قبل تدريب النموذج."""


def model_path(name: str = "xgboost") -> Path:
    if name not in MODEL_FILES:
        raise ValueError(f"نموذج غير معروف: {name}")
    return MODEL_FILES[name]


def is_model_available(name: str = "xgboost") -> bool:
    return model_path(name).exists()


def load_model(name: str = "xgboost", *, force_reload: bool = False):
    """تحميل الـ Pipeline المحفوظ (معالجة + نموذج) مع تخزين مؤقت آمن للخيوط."""
    path = model_path(name)
    with _LOCK:
        if force_reload:
            _CACHE.pop(name, None)
        cached = _CACHE.get(name)
        if cached is not None and path.exists() and cached["mtime"] == path.stat().st_mtime:
            return cached["pipeline"]
        if not path.exists():
            raise ModelNotTrainedError(
                "النموذج غير مدرَّب بعد. شغّل الأمر:  python -m app.ml.train"
            )
        pipeline = joblib.load(path)
        _CACHE[name] = {"pipeline": pipeline, "mtime": path.stat().st_mtime}
        return pipeline


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def classify_risk(probability: float) -> str:
    """تصنيف مستوى الخطورة إلى: low / medium / high."""
    if probability >= settings.RISK_HIGH_THRESHOLD:
        return "high"
    if probability >= settings.RISK_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def risk_label_ar(level: str) -> str:
    return RISK_LABELS_AR.get(level, level)


def predict_one(student: dict, model_name: str = "xgboost") -> dict:
    """تنبؤ لطالب واحد."""
    pipeline = load_model(model_name)
    X = prepare_features(student)
    proba = float(pipeline.predict_proba(X)[0, 1])
    level = classify_risk(proba)
    return {
        "model": model_name,
        "prediction": int(proba >= 0.5),
        "prediction_label": "معرّض للتسرب" if proba >= 0.5 else "غير معرّض للتسرب",
        "probability": round(proba, 4),
        "risk_level": level,
        "risk_level_ar": risk_label_ar(level),
    }


def predict_batch(df: pd.DataFrame, model_name: str = "xgboost") -> pd.DataFrame:
    """تنبؤ جماعي لجدول طلاب. يعيد جدولًا بالمعرف والتنبؤ والاحتمال ومستوى الخطورة."""
    pipeline = load_model(model_name)
    ids = (
        df[ID_COLUMN].astype(str).tolist()
        if ID_COLUMN in df.columns
        else [f"ROW-{i + 1}" for i in range(len(df))]
    )
    X = prepare_features(df)[FEATURE_ORDER]
    proba = pipeline.predict_proba(X)[:, 1].astype(float)
    levels = [classify_risk(p) for p in proba]
    return pd.DataFrame(
        {
            "student_id": ids,
            "prediction": (proba >= 0.5).astype(int),
            "probability": np.round(proba, 4),
            "risk_level": levels,
            "risk_level_ar": [risk_label_ar(v) for v in levels],
        }
    )
