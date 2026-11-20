"""تدريب النماذج: Logistic Regression (خط الأساس) و XGBoost (النموذج المعتمد).

التقسيم: 80% تدريب / 20% اختبار مع الحفاظ على توازن الفئات (Stratified).
يُحفظ كل نموذج مع معالِج الخصائص الخاص به داخل Pipeline واحد في مجلد models/.

التشغيل:  python -m app.ml.train
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from ..config import settings
from .evaluate import evaluate_model
from .features import FEATURE_ORDER, TARGET
from .preprocessing import build_preprocessor, clean_dataframe
from ..utils import utcnow

RANDOM_STATE = 42
TEST_SIZE = 0.20

XGB_MODEL_PATH = settings.MODELS_DIR / "xgboost_pipeline.joblib"
LOGREG_MODEL_PATH = settings.MODELS_DIR / "logistic_regression_pipeline.joblib"
METRICS_PATH = settings.MODELS_DIR / "metrics.json"
METADATA_PATH = settings.MODELS_DIR / "model_metadata.json"


def load_dataset(path: Path | None = None) -> pd.DataFrame:
    path = Path(path or settings.DATASET_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"لم يتم العثور على ملف البيانات: {path}\n"
            "شغّل أولًا:  python scripts/generate_dataset.py"
        )
    df = pd.read_csv(path)
    if TARGET not in df.columns:
        raise ValueError(f"ملف البيانات لا يحتوي على العمود الهدف «{TARGET}».")
    df = clean_dataframe(df, strict=False)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce").fillna(0).astype(int)
    return df


def build_logistic_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    C=1.0,
                    solver="lbfgs",
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def build_xgboost_pipeline(scale_pos_weight: float = 1.0) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "model",
                XGBClassifier(
                    n_estimators=180,
                    max_depth=3,
                    learning_rate=0.08,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    min_child_weight=6,
                    gamma=0.1,
                    reg_lambda=2.5,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    scale_pos_weight=scale_pos_weight,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                    tree_method="hist",
                ),
            ),
        ]
    )


def train(dataset_path: Path | None = None) -> dict:
    df = load_dataset(dataset_path)
    X = df[FEATURE_ORDER]
    y = df[TARGET].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    spw = (neg / pos) if pos > 0 else 1.0

    print(f"عدد صفوف التدريب: {len(X_train)} | عدد صفوف الاختبار: {len(X_test)}")

    logreg = build_logistic_pipeline()
    logreg.fit(X_train, y_train)
    logreg_metrics = evaluate_model(logreg, X_test, y_test)
    print("Logistic Regression:", json.dumps(logreg_metrics["metrics"], ensure_ascii=False))

    xgb = build_xgboost_pipeline(scale_pos_weight=spw)
    xgb.fit(X_train, y_train)
    xgb_metrics = evaluate_model(xgb, X_test, y_test)
    print("XGBoost:", json.dumps(xgb_metrics["metrics"], ensure_ascii=False))

    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(logreg, LOGREG_MODEL_PATH)
    joblib.dump(xgb, XGB_MODEL_PATH)

    # حفظ عيّنة خلفية لاستخدامها في SHAP
    background = X_train.sample(min(200, len(X_train)), random_state=RANDOM_STATE)
    background.to_csv(settings.MODELS_DIR / "shap_background.csv", index=False)

    payload = {
        "trained_at": utcnow().isoformat(timespec="seconds") + "Z",
        "dataset": str(dataset_path or settings.DATASET_PATH),
        "n_rows": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "test_size": TEST_SIZE,
        "positive_rate": float(np.mean(y)),
        "runtime_results": {
            "logistic_regression": logreg_metrics,
            "xgboost": xgb_metrics,
        },
    }
    METRICS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    METADATA_PATH.write_text(
        json.dumps(
            {
                "features": FEATURE_ORDER,
                "target": TARGET,
                "random_state": RANDOM_STATE,
                "xgboost_path": XGB_MODEL_PATH.name,
                "logistic_regression_path": LOGREG_MODEL_PATH.name,
                "trained_at": payload["trained_at"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"تم حفظ النماذج في: {settings.MODELS_DIR}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="تدريب نماذج نظام الإنذار المبكر")
    parser.add_argument("--dataset", type=str, default=None)
    args = parser.parse_args()
    train(Path(args.dataset) if args.dataset else None)


if __name__ == "__main__":
    main()
