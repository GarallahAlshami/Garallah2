"""مقارنة النماذج ومعلومات النموذج المدرَّب."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from ...config import settings
from ...db.models import User
from ...ml.evaluate import comparison_payload
from ...ml.features import CATEGORICAL_FEATURES, FEATURE_ORDER, NUMERIC_FEATURES
from ...ml.predict import is_model_available
from ..deps import require_permission

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/comparison")
def comparison(_: User = Depends(require_permission("models:view"))):
    """مقارنة Logistic Regression مقابل XGBoost.

    القسم `documented` يحتوي على النتائج الموثقة في تقرير المشروع كما هي.
    القسم `runtime` يحتوي على نتائج التدريب الفعلي في هذا التثبيت.
    """
    return comparison_payload()


@router.get("/info")
def model_info(_: User = Depends(require_permission("models:view"))):
    metadata_path = settings.MODELS_DIR / "model_metadata.json"
    metadata = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}

    return {
        "xgboost_available": is_model_available("xgboost"),
        "logistic_regression_available": is_model_available("logistic_regression"),
        "metadata": metadata,
        "pipeline": [
            "قراءة البيانات (CSV)",
            "التحقق والتنظيف (Validation & Cleaning)",
            "تعويض القيم المفقودة (Imputation)",
            "الترميز الثنائي للمتغيرات التصنيفية (One-Hot Encoding)",
            "التقييس للمتغيرات الرقمية (Standard Scaling)",
            "التدريب: 80% تدريب / 20% اختبار",
            "النمذجة: Logistic Regression و XGBoost",
            "التقييم: Accuracy / Precision / Recall / F1 / AUC-ROC",
            "التفسير: SHAP",
        ],
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "order": FEATURE_ORDER,
            "count": len(FEATURE_ORDER),
        },
        "risk_thresholds": {
            "medium": settings.RISK_MEDIUM_THRESHOLD,
            "high": settings.RISK_HIGH_THRESHOLD,
        },
    }
