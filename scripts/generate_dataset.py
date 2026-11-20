"""توليد مجموعة بيانات تجريبية (Synthetic Dataset) بنفس بنية حقول المشروع.

مهم: هذه بيانات تجريبية اصطناعية للتشغيل والاختبار فقط، وليست بيانات جامعية حقيقية.
عند توفر البيانات الحقيقية، استبدل ملف data/students_dataset.csv بنفس أسماء الأعمدة
وأعد تدريب النموذج بالأمر:  python -m app.ml.train
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.features import ALL_COLUMNS, CATEGORICAL_VALUES, TARGET  # noqa: E402

# درجة "ليونة" توليد التسمية: كلما زادت زاد التداخل بين الفئتين واقترب التوزيع
# من الواقع (لا يوجد فصل حتمي بين المتسرب وغير المتسرب).
LABEL_TEMPERATURE = 0.5


def generate(n: int = 3000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)


    # --- ديموغرافية
    age = np.clip(rng.normal(21.5, 2.6, n), 17, 45).round(0)
    gender = rng.choice(CATEGORICAL_VALUES["gender"], n, p=[0.52, 0.48])
    region = rng.choice(CATEGORICAL_VALUES["region"], n, p=[0.62, 0.38])
    income = rng.choice(CATEGORICAL_VALUES["family_income_level"], n, p=[0.38, 0.44, 0.18])
    parent_edu = rng.choice(CATEGORICAL_VALUES["parent_education"], n, p=[0.25, 0.45, 0.30])
    major = rng.choice(CATEGORICAL_VALUES["major"], n, p=[0.26, 0.24, 0.20, 0.18, 0.12])

    # --- أكاديمية
    study_year = rng.integers(1, 6, n)
    admission_score = np.clip(rng.normal(76, 9, n), 50, 100).round(1)
    ability = (admission_score - 76) / 9.0  # قدرة كامنة

    income_boost = np.select(
        [income == "low", income == "medium", income == "high"], [-0.28, 0.0, 0.22]
    )
    edu_boost = np.select(
        [parent_edu == "none", parent_edu == "secondary", parent_edu == "university"],
        [-0.22, 0.0, 0.20],
    )
    rural_penalty = np.where(region == "rural", -0.16, 0.0)

    latent = ability + income_boost + edu_boost + rural_penalty + rng.normal(0, 0.7, n)

    gpa = np.clip(2.55 + 0.42 * latent + rng.normal(0, 0.32, n), 0.0, 4.0).round(2)
    previous_gpa = np.clip(gpa + rng.normal(0.08, 0.30, n), 0.0, 4.0).round(2)
    credits_completed = np.clip(
        (study_year * 30) + rng.normal(0, 9, n) + (gpa - 2.5) * 6, 0, 200
    ).round(0)
    failed_courses = np.clip(
        rng.poisson(np.clip(4.2 - 1.05 * gpa, 0.05, 6.0)), 0, 30
    )
    scholarship = np.where(
        (gpa > 3.2) & (rng.random(n) < 0.55), "yes",
        np.where(rng.random(n) < 0.07, "yes", "no"),
    )

    # --- سلوكية
    engagement = 0.62 * latent + rng.normal(0, 0.75, n)
    attendance_rate = np.clip(78 + 8.5 * engagement + rng.normal(0, 6, n), 0, 100).round(1)
    lms_logins = np.clip(
        rng.poisson(np.clip(7 + 2.6 * engagement, 0.2, 40)), 0, 60
    )
    assignment_rate = np.clip(80 + 8.0 * engagement + rng.normal(0, 8, n), 0, 100).round(1)
    avg_session = np.clip(35 + 11 * engagement + rng.normal(0, 10, n), 0, 300).round(1)
    forum_posts = np.clip(rng.poisson(np.clip(5 + 2.4 * engagement, 0.1, 40)), 0, 200)
    late_submissions = np.clip(
        rng.poisson(np.clip(6.5 - 1.9 * engagement, 0.05, 25)), 0, 60
    )
    advisor_meetings = np.clip(rng.poisson(np.clip(2.0 + 0.5 * engagement, 0.05, 12)), 0, 20)
    financial_default = np.where(
        (income == "low") & (rng.random(n) < 0.34), "yes",
        np.where(rng.random(n) < 0.06, "yes", "no"),
    )

    # --- المتغير الهدف: التسرب
    # علاقات خطية + تفاعلات غير خطية (تُظهر تفوق النماذج الشجرية على الخطية)
    interaction = (
        3.60 * ((gpa < 2.2) & (attendance_rate < 72))
        + 2.90 * ((failed_courses >= 4) & (lms_logins < 5))
        + 2.40 * ((financial_default == "yes") & (income == "low"))
        + 2.10 * ((late_submissions > 8) & (assignment_rate < 70))
        - 3.10 * ((gpa > 3.1) & (attendance_rate > 86))
        - 2.30 * ((advisor_meetings >= 3) & (assignment_rate > 85))
        + 1.60 * ((age > 26) & (study_year <= 2))
    )
    z = (
        -2.05
        - 0.70 * (gpa - 2.5)
        - 0.026 * (attendance_rate - 78)
        - 0.030 * (assignment_rate - 80)
        - 0.085 * (lms_logins - 7)
        + 0.175 * failed_courses
        + 0.070 * late_submissions
        - 0.130 * advisor_meetings
        + 0.75 * (financial_default == "yes")
        - 0.55 * (scholarship == "yes")
        + 0.30 * (income == "low")
        + 0.22 * (region == "rural")
        - 0.012 * (avg_session - 35)
        + interaction
        + rng.normal(0, 0.30, n)
    )
    # نموذج توليدي احتمالي: يُشتق احتمال التسرب الحقيقي من الدالة اللوجستية،
    # ثم تُسحب الحالة الفعلية عشوائيًا منه. هذا يجعل المشكلة قابلة للتعلّم دون أن
    # تكون حتمية، ويمنح النموذج المدرَّب توزيعًا متدرّجًا للاحتمالات بدل قيم متطرفة.
    true_probability = 1.0 / (1.0 + np.exp(-z / LABEL_TEMPERATURE))
    dropout = (rng.random(n) < true_probability).astype(int)

    df = pd.DataFrame(
        {
            "student_id": [f"STU{2020 + int(y) % 5}{i:05d}" for i, y in enumerate(study_year, start=1)],
            "age": age.astype(int),
            "gpa": gpa,
            "previous_gpa": previous_gpa,
            "admission_score": admission_score,
            "credits_completed": credits_completed.astype(int),
            "failed_courses": failed_courses.astype(int),
            "study_year": study_year.astype(int),
            "attendance_rate": attendance_rate,
            "lms_logins_per_week": lms_logins.astype(int),
            "assignment_submission_rate": assignment_rate,
            "avg_session_minutes": avg_session,
            "forum_posts": forum_posts.astype(int),
            "late_submissions": late_submissions.astype(int),
            "advisor_meetings": advisor_meetings.astype(int),
            "gender": gender,
            "region": region,
            "family_income_level": income,
            "parent_education": parent_edu,
            "major": major,
            "scholarship": scholarship,
            "financial_default": financial_default,
            TARGET: dropout,
        }
    )
    return df[ALL_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(description="توليد بيانات تجريبية للنظام")
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out", type=str,
        default=str(Path(__file__).resolve().parent.parent / "data" / "students_dataset.csv"),
    )
    args = parser.parse_args()

    df = generate(args.rows, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")

    # عيّنة صغيرة جاهزة للتحليل الجماعي (بدون عمود الهدف)
    sample = df.drop(columns=[TARGET]).sample(60, random_state=7)
    sample.to_csv(out.parent / "sample_batch.csv", index=False, encoding="utf-8-sig")

    print(f"تم إنشاء الملف: {out}  ({len(df)} صفًا)")
    print(f"نسبة التسرب في البيانات: {df[TARGET].mean():.2%}")
    print(f"ملف عيّنة التحليل الجماعي: {out.parent / 'sample_batch.csv'}")


if __name__ == "__main__":
    main()
