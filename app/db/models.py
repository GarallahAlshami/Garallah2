"""نماذج قاعدة البيانات (ORM).

الجداول: users, students, predictions, risk_factors, recommendations, reports, system_logs
ملاحظة أمنية: لا تُخزَّن كلمات المرور نصًا صريحًا، بل تُخزَّن بصمة PBKDF2-SHA256.
ولا تُخزَّن أي بيانات شخصية حساسة غير ضرورية لعمل النظام.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from ..utils import utcnow


def _now() -> datetime:
    return utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="advisor")  # admin | advisor
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="created_by")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    # ---- ديموغرافية
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="male")
    region: Mapped[str] = mapped_column(String(16), nullable=False, default="urban")
    family_income_level: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    parent_education: Mapped[str] = mapped_column(String(24), nullable=False, default="secondary")

    # ---- أكاديمية
    major: Mapped[str] = mapped_column(String(48), nullable=False, default="information_systems")
    study_year: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    gpa: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    previous_gpa: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    admission_score: Mapped[float] = mapped_column(Float, nullable=False, default=75.0)
    credits_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_courses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scholarship: Mapped[str] = mapped_column(String(8), nullable=False, default="no")

    # ---- سلوكية
    attendance_rate: Mapped[float] = mapped_column(Float, nullable=False, default=80.0)
    lms_logins_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    assignment_submission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=80.0)
    avg_session_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    forum_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    advisor_meetings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    financial_default: Mapped[str] = mapped_column(String(8), nullable=False, default="no")

    # ---- آخر نتيجة تنبؤ (نسخة مخزنة للعرض السريع في لوحة التحكم)
    last_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_predicted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_pk: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    student_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(48), nullable=False, default="xgboost")
    prediction: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="single")  # single | batch
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False, index=True)

    student: Mapped["Student | None"] = relationship(back_populates="predictions")
    created_by: Mapped["User | None"] = relationship(back_populates="predictions")
    factors: Mapped[list["RiskFactor"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class RiskFactor(Base):
    """عوامل الخطر المستخرجة من SHAP لكل عملية تنبؤ."""

    __tablename__ = "risk_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature: Mapped[str] = mapped_column(String(96), nullable=False)
    feature_ar: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    shap_value: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # increase | decrease
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    prediction: Mapped["Prediction"] = relationship(back_populates="factors")


class Recommendation(Base):
    """قواعد التوصيات الإرشادية — قابلة للتوسعة دون تعديل الكود."""

    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("code", name="uq_recommendation_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    feature: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(8), nullable=False, default="<")  # < | > | == 
    threshold: Mapped[str] = mapped_column(String(48), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    action_ar: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="academic")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)  # 1 عالية .. 3 منخفضة
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_format: Mapped[str] = mapped_column(String(8), nullable=False, default="csv")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False, index=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="-")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False, index=True)
