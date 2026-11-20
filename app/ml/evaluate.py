"""تقييم النماذج: Accuracy / Precision / Recall / F1-Score / AUC-ROC + مصفوفة الالتباس."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from ..config import settings

# ---------------------------------------------------------------------------
# النتائج الموثقة في تقرير المشروع النهائي — قيم ثابتة لا تُعدَّل برمجيًا.
# ---------------------------------------------------------------------------
DOCUMENTED_RESULTS: dict[str, dict[str, float]] = {
    "logistic_regression": {
        "accuracy": 0.83,
        "precision": 0.76,
        "recall": 0.75,
        "f1": 0.78,
        "auc_roc": 0.81,
    },
    "xgboost": {
        "accuracy": 0.97,
        "precision": 0.91,
        "recall": 0.91,
        "f1": 0.92,
        "auc_roc": 0.94,
    },
}

MODEL_LABELS_AR = {
    "logistic_regression": "الانحدار اللوجستي (Logistic Regression)",
    "xgboost": "XGBoost",
}

METRIC_LABELS_AR = {
    "accuracy": "الدقة الكلية (Accuracy)",
    "precision": "الإحكام (Precision)",
    "recall": "الاستدعاء (Recall)",
    "f1": "المتوسط التوافقي (F1-Score)",
    "auc_roc": "المساحة تحت المنحنى (AUC-ROC)",
}


def evaluate_model(pipeline, X_test, y_test) -> dict:
    """حساب مقاييس الأداء لنموذج مدرَّب على مجموعة الاختبار."""
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    step = max(1, len(fpr) // 100)

    return {
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "auc_roc": round(float(roc_auc_score(y_test, y_proba)), 4),
        },
        "confusion_matrix": cm.tolist(),
        "roc_curve": {
            "fpr": [round(float(v), 4) for v in fpr[::step]] + [1.0],
            "tpr": [round(float(v), 4) for v in tpr[::step]] + [1.0],
        },
        "support": int(len(np.asarray(y_test))),
    }


def load_runtime_metrics() -> dict | None:
    """قراءة نتائج آخر تدريب فعلي من models/metrics.json."""
    path: Path = settings.MODELS_DIR / "metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def comparison_payload() -> dict:
    """حزمة المقارنة المعروضة في صفحة مقارنة النماذج."""
    runtime = load_runtime_metrics()
    return {
        "documented": DOCUMENTED_RESULTS,
        "documented_note": (
            "هذه هي النتائج الموثقة في تقرير المشروع النهائي وتُعرض كما هي دون أي تعديل."
        ),
        "runtime": (runtime or {}).get("runtime_results"),
        "runtime_note": (
            "نتائج التشغيل الحالي محسوبة على مجموعة الاختبار (20%) من البيانات "
            "المستخدمة فعليًا في هذا التثبيت، وتُعرض للشفافية بجانب النتائج الموثقة."
        ),
        "trained_at": (runtime or {}).get("trained_at"),
        "n_train": (runtime or {}).get("n_train"),
        "n_test": (runtime or {}).get("n_test"),
        "model_labels": MODEL_LABELS_AR,
        "metric_labels": METRIC_LABELS_AR,
    }
