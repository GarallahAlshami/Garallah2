"""تعريف مخطط الخصائص (Feature Schema) المستخدم في التدريب والتنبؤ.

هذا الملف هو المصدر الوحيد للحقيقة (Single Source of Truth) لبنية بيانات الطالب،
ويُستخدم في: توليد البيانات، المعالجة المسبقة، قاعدة البيانات، التحقق من ملفات CSV،
وواجهة النظام. أي تعديل على الحقول يتم هنا فقط.

الحقول مقسّمة إلى ثلاث مجموعات كما هو موصوف في منهجية المشروع:
    1) بيانات ديموغرافية   Demographic
    2) بيانات أكاديمية     Academic
    3) بيانات سلوكية       Behavioral
"""
from __future__ import annotations

from typing import Any

TARGET = "dropout"
ID_COLUMN = "student_id"

# ---------------------------------------------------------------- الخصائص الرقمية
NUMERIC_FEATURES: list[str] = [
    # ديموغرافية
    "age",
    # أكاديمية
    "gpa",
    "previous_gpa",
    "admission_score",
    "credits_completed",
    "failed_courses",
    "study_year",
    # سلوكية
    "attendance_rate",
    "lms_logins_per_week",
    "assignment_submission_rate",
    "avg_session_minutes",
    "forum_posts",
    "late_submissions",
    "advisor_meetings",
]

# ------------------------------------------------------------- الخصائص التصنيفية
CATEGORICAL_FEATURES: list[str] = [
    "gender",
    "region",
    "family_income_level",
    "parent_education",
    "major",
    "scholarship",
    "financial_default",
]

CATEGORICAL_VALUES: dict[str, list[str]] = {
    "gender": ["male", "female"],
    "region": ["urban", "rural"],
    "family_income_level": ["low", "medium", "high"],
    "parent_education": ["none", "secondary", "university"],
    "major": ["information_systems", "computer_science", "business", "engineering", "medicine"],
    "scholarship": ["yes", "no"],
    "financial_default": ["yes", "no"],
}

FEATURE_ORDER: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES
ALL_COLUMNS: list[str] = [ID_COLUMN] + FEATURE_ORDER + [TARGET]

# ------------------------------------------------------------------ حدود التحقق
NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "age": (16, 60),
    "gpa": (0.0, 4.0),
    "previous_gpa": (0.0, 4.0),
    "admission_score": (50.0, 100.0),
    "credits_completed": (0, 200),
    "failed_courses": (0, 30),
    "study_year": (1, 6),
    "attendance_rate": (0.0, 100.0),
    "lms_logins_per_week": (0, 60),
    "assignment_submission_rate": (0.0, 100.0),
    "avg_session_minutes": (0.0, 300.0),
    "forum_posts": (0, 200),
    "late_submissions": (0, 60),
    "advisor_meetings": (0, 20),
}

# ------------------------------------------------------------ التسميات العربية
FEATURE_LABELS_AR: dict[str, str] = {
    "age": "العمر",
    "gpa": "المعدل التراكمي الحالي",
    "previous_gpa": "المعدل التراكمي السابق",
    "admission_score": "درجة القبول",
    "credits_completed": "الساعات المعتمدة المنجزة",
    "failed_courses": "عدد المقررات الراسب فيها",
    "study_year": "السنة الدراسية",
    "attendance_rate": "نسبة الحضور (%)",
    "lms_logins_per_week": "مرات الدخول لمنصة التعلم أسبوعيًا",
    "assignment_submission_rate": "نسبة تسليم الواجبات (%)",
    "avg_session_minutes": "متوسط زمن الجلسة (دقيقة)",
    "forum_posts": "مشاركات المنتدى",
    "late_submissions": "التسليمات المتأخرة",
    "advisor_meetings": "لقاءات المرشد الأكاديمي",
    "gender": "الجنس",
    "region": "مكان السكن",
    "family_income_level": "مستوى دخل الأسرة",
    "parent_education": "تعليم ولي الأمر",
    "major": "التخصص",
    "scholarship": "منحة دراسية",
    "financial_default": "تعثر مالي",
}

VALUE_LABELS_AR: dict[str, str] = {
    "male": "ذكر",
    "female": "أنثى",
    "urban": "حضر",
    "rural": "ريف",
    "low": "منخفض",
    "medium": "متوسط",
    "high": "مرتفع",
    "none": "بدون",
    "secondary": "ثانوي",
    "university": "جامعي",
    "information_systems": "نظم المعلومات",
    "computer_science": "علوم الحاسوب",
    "business": "إدارة أعمال",
    "engineering": "هندسة",
    "medicine": "طب",
    "yes": "نعم",
    "no": "لا",
}

FEATURE_GROUPS_AR: dict[str, list[str]] = {
    "بيانات ديموغرافية": ["age", "gender", "region", "family_income_level", "parent_education"],
    "بيانات أكاديمية": [
        "major", "study_year", "gpa", "previous_gpa", "admission_score",
        "credits_completed", "failed_courses", "scholarship",
    ],
    "بيانات سلوكية": [
        "attendance_rate", "lms_logins_per_week", "assignment_submission_rate",
        "avg_session_minutes", "forum_posts", "late_submissions",
        "advisor_meetings", "financial_default",
    ],
}


def label_ar(feature: str) -> str:
    """اسم الخاصية بالعربية (يدعم أسماء ما بعد الترميز مثل major_business)."""
    if feature in FEATURE_LABELS_AR:
        return FEATURE_LABELS_AR[feature]
    for cat in CATEGORICAL_FEATURES:
        prefix = f"{cat}_"
        if feature.startswith(prefix):
            value = feature[len(prefix):]
            return f"{FEATURE_LABELS_AR[cat]}: {VALUE_LABELS_AR.get(value, value)}"
    return feature


def value_label_ar(value: Any) -> str:
    return VALUE_LABELS_AR.get(str(value), str(value))
