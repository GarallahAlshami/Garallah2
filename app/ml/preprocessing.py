"""المعالجة المسبقة للبيانات — تُستخدم بنفس الشكل أثناء التدريب والتنبؤ.

يتم بناء Pipeline من scikit-learn يضم:
    * One-Hot Encoding للمتغيرات التصنيفية
    * Standard Scaling للمتغيرات الرقمية
    * معالجة القيم المفقودة (Imputation)

وبما أن نفس كائن الـ Pipeline يُحفظ مع النموذج ويُعاد تحميله وقت التنبؤ،
فإن ذلك يمنع تسرب البيانات (Data Leakage) واختلاف المعالجة بين المرحلتين.
"""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import (
    CATEGORICAL_FEATURES,
    CATEGORICAL_VALUES,
    FEATURE_ORDER,
    ID_COLUMN,
    NUMERIC_BOUNDS,
    NUMERIC_FEATURES,
    TARGET,
)


class DataValidationError(ValueError):
    """خطأ في التحقق من صحة البيانات المدخلة."""


def _one_hot_encoder() -> OneHotEncoder:
    categories = [CATEGORICAL_VALUES[c] for c in CATEGORICAL_FEATURES]
    try:  # scikit-learn >= 1.2
        return OneHotEncoder(categories=categories, handle_unknown="ignore", sparse_output=False)
    except TypeError:  # scikit-learn < 1.2
        return OneHotEncoder(categories=categories, handle_unknown="ignore", sparse=False)


def build_preprocessor() -> ColumnTransformer:
    """بناء معالِج الخصائص (Encoding + Scaling)."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", _one_hot_encoder()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """أسماء الخصائص بعد الترميز (تُستخدم في SHAP)."""
    try:
        return [str(n) for n in preprocessor.get_feature_names_out()]
    except Exception:  # pragma: no cover - مسار احتياطي
        names = list(NUMERIC_FEATURES)
        for col in CATEGORICAL_FEATURES:
            names += [f"{col}_{v}" for v in CATEGORICAL_VALUES[col]]
        return names


# ------------------------------------------------------------------ التنظيف
def clean_dataframe(df: pd.DataFrame, *, strict: bool = False) -> pd.DataFrame:
    """تنظيف وتوحيد البيانات: أنواع صحيحة، قيم تصنيفية معروفة، قصّ القيم الشاذة."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in FEATURE_ORDER if c not in df.columns]
    if missing:
        raise DataValidationError("أعمدة مفقودة في البيانات: " + ", ".join(missing))

    for col in NUMERIC_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        low, high = NUMERIC_BOUNDS[col]
        df[col] = df[col].clip(lower=low, upper=high)

    for col in CATEGORICAL_FEATURES:
        df[col] = (
            df[col].astype(str).str.strip().str.lower().str.replace(" ", "_", regex=False)
        )
        allowed = set(CATEGORICAL_VALUES[col])
        invalid_mask = ~df[col].isin(allowed)
        if invalid_mask.any():
            if strict:
                bad = sorted(df.loc[invalid_mask, col].unique())[:5]
                raise DataValidationError(
                    f"قيم غير مسموح بها في العمود «{col}»: {bad}. "
                    f"القيم المسموحة: {sorted(allowed)}"
                )
            df.loc[invalid_mask, col] = pd.Series(
                [CATEGORICAL_VALUES[col][0]] * int(invalid_mask.sum()), index=df.index[invalid_mask]
            )

    if ID_COLUMN in df.columns:
        df[ID_COLUMN] = df[ID_COLUMN].astype(str).str.strip()

    return df


def validate_batch_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """التحقق من ملف CSV الخاص بالتحليل الجماعي.

    يعيد: (إطار بيانات نظيف، قائمة تحذيرات).
    """
    warnings: list[str] = []
    if df.empty:
        raise DataValidationError("الملف فارغ ولا يحتوي على أي صفوف.")
    if len(df) > 20000:
        raise DataValidationError("عدد الصفوف يتجاوز الحد المسموح (20000 صف).")

    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in FEATURE_ORDER if c not in df.columns]
    if missing:
        raise DataValidationError(
            "الملف لا يحتوي على الأعمدة المطلوبة التالية: " + "، ".join(missing)
        )

    if ID_COLUMN not in df.columns:
        warnings.append("لا يوجد عمود student_id — سيتم توليد معرفات تلقائية.")
        df[ID_COLUMN] = [f"ROW-{i + 1}" for i in range(len(df))]

    before = len(df)
    df = df.dropna(subset=[ID_COLUMN])
    df = df.drop_duplicates(subset=[ID_COLUMN], keep="first")
    if len(df) < before:
        warnings.append(f"تم حذف {before - len(df)} صفًا مكررًا أو بدون معرف طالب.")

    numeric_na = 0
    for col in NUMERIC_FEATURES:
        numeric_na += int(pd.to_numeric(df[col], errors="coerce").isna().sum())
    if numeric_na:
        warnings.append(f"تم العثور على {numeric_na} قيمة رقمية مفقودة/غير صالحة وسيتم تعويضها.")

    cleaned = clean_dataframe(df, strict=False)
    keep = [ID_COLUMN] + FEATURE_ORDER + ([TARGET] if TARGET in df.columns else [])
    return cleaned[keep], warnings


def prepare_features(data: pd.DataFrame | dict) -> pd.DataFrame:
    """تحويل مدخل (صف واحد أو جدول) إلى إطار خصائص جاهز للنموذج."""
    if isinstance(data, dict):
        data = pd.DataFrame([data])
    cleaned = clean_dataframe(data, strict=False)
    return cleaned[FEATURE_ORDER]
