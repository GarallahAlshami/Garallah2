"""تهيئة قاعدة البيانات: إنشاء الجداول، المستخدمين الافتراضيين، قواعد التوصيات،
واستيراد الطلاب من ملف البيانات.

التشغيل:  python -m app.db.seed
"""
from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy.orm import Session

from ..config import settings
from ..ml.features import CATEGORICAL_FEATURES, FEATURE_ORDER, NUMERIC_FEATURES
from ..security import hash_password
from ..services.recommendations import seed_recommendations
from .database import SessionLocal, init_db
from .models import Student, SystemLog, User

STUDENT_NAME_PREFIX = "طالب"


def seed_users(db: Session) -> list[str]:
    created: list[str] = []
    defaults = [
        {
            "username": settings.DEFAULT_ADMIN_USERNAME,
            "email": settings.DEFAULT_ADMIN_EMAIL,
            "full_name": "مدير النظام",
            "password": settings.DEFAULT_ADMIN_PASSWORD,
            "role": "admin",
        },
        {
            "username": settings.DEFAULT_ADVISOR_USERNAME,
            "email": settings.DEFAULT_ADVISOR_EMAIL,
            "full_name": "المرشد الأكاديمي",
            "password": settings.DEFAULT_ADVISOR_PASSWORD,
            "role": "advisor",
        },
    ]
    for item in defaults:
        exists = db.query(User).filter(User.username == item["username"]).first()
        if exists:
            continue
        db.add(
            User(
                username=item["username"],
                email=item["email"],
                full_name=item["full_name"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                is_active=True,
            )
        )
        created.append(item["username"])
    if created:
        db.commit()
    return created


def seed_students(db: Session, limit: int = 400) -> int:
    """استيراد عيّنة من الطلاب من ملف البيانات إلى قاعدة البيانات."""
    if db.query(Student).count() > 0:
        return 0
    if not settings.DATASET_PATH.exists():
        return 0

    df = pd.read_csv(settings.DATASET_PATH)
    df = df.head(limit)
    added = 0
    for i, row in df.iterrows():
        payload = {col: row[col] for col in FEATURE_ORDER if col in df.columns}
        for col in NUMERIC_FEATURES:
            if col in payload:
                payload[col] = float(payload[col])
        for col in CATEGORICAL_FEATURES:
            if col in payload:
                payload[col] = str(payload[col])
        for int_col in (
            "age", "study_year", "credits_completed", "failed_courses",
            "lms_logins_per_week", "forum_posts", "late_submissions", "advisor_meetings",
        ):
            if int_col in payload:
                payload[int_col] = int(payload[int_col])

        db.add(
            Student(
                student_id=str(row["student_id"]),
                full_name=f"{STUDENT_NAME_PREFIX} رقم {i + 1}",
                **payload,
            )
        )
        added += 1
    db.commit()
    return added


def run_seed(students_limit: int = 400) -> dict[str, int | list[str]]:
    """تهيئة الجداول وإدخال البيانات الأولية (تستخدمها الواجهة الطرفية والاختبارات)."""
    init_db()
    db = SessionLocal()
    try:
        users = seed_users(db)
        rules = seed_recommendations(db)
        students = seed_students(db, students_limit)
        db.add(
            SystemLog(
                username="system",
                action="db_seed",
                entity="database",
                details=f"users={len(users)} rules={rules} students={students}",
            )
        )
        db.commit()
        return {"users": users, "rules": rules, "students": students}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="تهيئة قاعدة بيانات النظام")
    parser.add_argument("--students", type=int, default=400, help="عدد الطلاب المستوردين")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        users = seed_users(db)
        rules = seed_recommendations(db)
        students = seed_students(db, args.students)
        db.add(
            SystemLog(
                username="system",
                action="db_seed",
                entity="database",
                details=f"users={len(users)} rules={rules} students={students}",
            )
        )
        db.commit()
        print("تمت تهيئة قاعدة البيانات بنجاح.")
        print(f"  المستخدمون المضافون: {users or 'لا يوجد (موجودون مسبقًا)'}")
        print(f"  قواعد التوصيات المضافة: {rules}")
        print(f"  الطلاب المستوردون: {students}")
        print(f"  مسار قاعدة البيانات: {settings.DATABASE_URL}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
