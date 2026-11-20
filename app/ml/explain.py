"""الذكاء الاصطناعي القابل للتفسير (Explainable AI) باستخدام SHAP.

يوفّر:
    * تفسير فردي لطالب  (Waterfall / Bar)
    * الأهمية العامة للخصائص (Global Feature Importance)
    * إخراج رقمي (JSON) لبناء الرسوم داخل الواجهة + صور PNG جاهزة
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402

from ..config import settings  # noqa: E402
from .features import FEATURE_ORDER, label_ar  # noqa: E402
from .predict import load_model  # noqa: E402
from .preprocessing import get_feature_names, prepare_features  # noqa: E402

_LOCK = threading.Lock()
_EXPLAINER: dict[str, object] = {}

PLOTS_DIR = settings.REPORTS_DIR / "shap_plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def _background() -> pd.DataFrame | None:
    path = settings.MODELS_DIR / "shap_background.csv"
    if path.exists():
        try:
            return pd.read_csv(path)[FEATURE_ORDER]
        except Exception:
            return None
    return None


def get_explainer(model_name: str = "xgboost"):
    """بناء (أو استرجاع) كائن SHAP TreeExplainer الخاص بالنموذج."""
    with _LOCK:
        if model_name in _EXPLAINER:
            return _EXPLAINER[model_name]
        pipeline = load_model(model_name)
        booster = pipeline.named_steps["model"]
        explainer = shap.TreeExplainer(booster)
        _EXPLAINER[model_name] = explainer
        return explainer


def clear_cache() -> None:
    with _LOCK:
        _EXPLAINER.clear()


def _transform(pipeline, X: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    pre = pipeline.named_steps["preprocessor"]
    Xt = pre.transform(X)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    return np.asarray(Xt, dtype=float), get_feature_names(pre)


def explain_student(student: dict, model_name: str = "xgboost", top_k: int = 10) -> dict:
    """تفسير تنبؤ طالب واحد.

    يعيد قائمة العوامل التي رفعت الخطر (قيم SHAP الموجبة) والتي خفّضته (السالبة)،
    مع مقدار تأثير كل متغيّر.
    """
    pipeline = load_model(model_name)
    X = prepare_features(student)[FEATURE_ORDER]
    Xt, names = _transform(pipeline, X)

    explainer = get_explainer(model_name)
    shap_values = np.asarray(explainer.shap_values(Xt))
    if shap_values.ndim == 3:  # بعض الإصدارات تعيد بعدًا لكل فئة
        shap_values = shap_values[..., -1]
    row = shap_values[0]

    base_value = explainer.expected_value
    if isinstance(base_value, (list, np.ndarray)):
        base_value = float(np.asarray(base_value).ravel()[-1])
    base_value = float(base_value)

    raw = X.iloc[0].to_dict()
    contributions = []
    for name, value, shap_val in zip(names, Xt[0], row):
        contributions.append(
            {
                "feature": name,
                "feature_ar": label_ar(name),
                "encoded_value": round(float(value), 4),
                "raw_value": _raw_value_for(name, raw),
                "shap_value": round(float(shap_val), 5),
                "abs_shap": abs(float(shap_val)),
                "direction": "increase" if shap_val > 0 else ("decrease" if shap_val < 0 else "neutral"),
            }
        )

    contributions.sort(key=lambda d: d["abs_shap"], reverse=True)
    top = contributions[:top_k]
    increasing = [c for c in top if c["direction"] == "increase"]
    decreasing = [c for c in top if c["direction"] == "decrease"]

    return {
        "model": model_name,
        "base_value": round(base_value, 5),
        "output_value": round(base_value + float(row.sum()), 5),
        "top_factors": top,
        "increasing_risk": increasing,
        "decreasing_risk": decreasing,
        "all_factors": contributions,
    }


def _raw_value_for(encoded_name: str, raw: dict):
    if encoded_name in raw:
        value = raw[encoded_name]
        return float(value) if isinstance(value, (int, float, np.number)) else str(value)
    for col, value in raw.items():
        if isinstance(value, str) and encoded_name == f"{col}_{value}":
            return "نعم"
    return None


def global_importance(model_name: str = "xgboost", top_k: int = 15, sample: int = 300) -> dict:
    """الأهمية العامة للخصائص عبر عيّنة من البيانات (متوسط |SHAP|)."""
    pipeline = load_model(model_name)
    bg = _background()
    if bg is None:
        raise FileNotFoundError(
            "ملف العينة الخلفية غير موجود. أعد تدريب النموذج:  python -m app.ml.train"
        )
    bg = bg.sample(min(sample, len(bg)), random_state=42)
    Xt, names = _transform(pipeline, bg)
    explainer = get_explainer(model_name)
    values = np.asarray(explainer.shap_values(Xt))
    if values.ndim == 3:
        values = values[..., -1]
    mean_abs = np.abs(values).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:top_k]
    return {
        "model": model_name,
        "sample_size": int(len(bg)),
        "features": [
            {
                "feature": names[i],
                "feature_ar": label_ar(names[i]),
                "mean_abs_shap": round(float(mean_abs[i]), 5),
            }
            for i in order
        ],
    }


# ----------------------------------------------------------------- رسوم PNG
def _matplotlib_shapes_arabic() -> bool:
    """هل تدعم نسخة matplotlib الحالية تشكيل الحروف العربية تلقائيًا؟

    الإصدارات الحديثة من matplotlib تعتمد على libraqm/harfbuzz فتتولى الوصل
    والاتجاه بنفسها، وعندها يجب تمرير النص العربي كما هو. أما الإصدارات
    القديمة فلا تُشكّل الحروف، ويلزم تحويل النص يدويًا عبر arabic_reshaper
    وخوارزمية bidi. التحقق يتم مرة واحدة عند تحميل الوحدة.
    """
    if os.getenv("EWS_MANUAL_ARABIC_SHAPING", "").strip() in {"1", "true", "True"}:
        return False
    try:
        import matplotlib.ft2font as ft2font

        # وجود libraqm يعني أن matplotlib تتولى الوصل والاتجاه للنص العربي
        return bool(getattr(ft2font, "__libraqm_version__", ""))
    except Exception:  # pragma: no cover
        return False


_AUTO_SHAPING = _matplotlib_shapes_arabic()


def _ar(text: str) -> str:
    """تهيئة النص العربي ليُعرض بشكل صحيح داخل matplotlib.

    عند توفر التشكيل التلقائي يُمرَّر النص كما هو (وإلا ظهر مقلوبًا ومنفصل
    الحروف بسبب التشكيل المزدوج)، وعند غيابه يُحوَّل يدويًا.
    """
    if _AUTO_SHAPING:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:  # pragma: no cover
        return text


def _configure_arabic_font() -> None:
    font_path = settings.ASSETS_DIR / "fonts" / "Arabic-Regular.ttf"
    if font_path.exists():
        try:
            from matplotlib import font_manager

            font_manager.fontManager.addfont(str(font_path))
            name = font_manager.FontProperties(fname=str(font_path)).get_name()
            plt.rcParams["font.family"] = name
        except Exception:  # pragma: no cover
            pass


_configure_arabic_font()


def waterfall_png(student: dict, out_path: Path | None = None, top_k: int = 10) -> Path:
    """رسم SHAP Waterfall لطالب واحد وحفظه كصورة PNG."""
    result = explain_student(student, top_k=top_k)
    factors = list(reversed(result["top_factors"]))
    labels = [_ar(f["feature_ar"]) for f in factors]
    values = [f["shap_value"] for f in factors]
    colors = ["#c0392b" if v > 0 else "#1a7f5a" for v in values]

    fig, ax = plt.subplots(figsize=(9, 0.52 * len(factors) + 2))
    ax.barh(labels, values, color=colors)
    ax.axvline(0, color="#555", linewidth=1)
    ax.set_xlabel(_ar("مقدار تأثير المتغير على مخرجات النموذج (قيمة SHAP)"))
    ax.set_title(_ar("تفسير التنبؤ للطالب — SHAP"))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()

    out_path = Path(out_path or (PLOTS_DIR / "waterfall.png"))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def importance_png(out_path: Path | None = None, top_k: int = 15) -> Path:
    """رسم الأهمية العامة للخصائص وحفظه كصورة PNG."""
    data = global_importance(top_k=top_k)
    feats = list(reversed(data["features"]))
    labels = [_ar(f["feature_ar"]) for f in feats]
    values = [f["mean_abs_shap"] for f in feats]

    fig, ax = plt.subplots(figsize=(9, 0.5 * len(feats) + 2))
    ax.barh(labels, values, color="#2c5f8a")
    ax.set_xlabel(_ar("متوسط القيمة المطلقة لـ SHAP"))
    ax.set_title(_ar("الأهمية العامة للخصائص — SHAP Feature Importance"))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()

    out_path = Path(out_path or (PLOTS_DIR / "importance.png"))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
