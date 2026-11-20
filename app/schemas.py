"""مخططات التحقق من المدخلات والمخرجات (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .ml.features import CATEGORICAL_VALUES, NUMERIC_BOUNDS

Role = Literal["admin", "advisor"]


# ------------------------------------------------------------------ المصادقة
class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=160, description="اسم المستخدم أو البريد")
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    permissions: list[str]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(default="", max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "advisor"


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=160)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ------------------------------------------------------------------- الطلاب
def _bound(name: str) -> tuple[float, float]:
    return NUMERIC_BOUNDS[name]


class StudentBase(BaseModel):
    full_name: str = Field(default="", max_length=160)

    age: int = Field(ge=_bound("age")[0], le=_bound("age")[1])
    gender: str
    region: str
    family_income_level: str
    parent_education: str

    major: str
    study_year: int = Field(ge=1, le=6)
    gpa: float = Field(ge=0.0, le=4.0)
    previous_gpa: float = Field(ge=0.0, le=4.0)
    admission_score: float = Field(ge=50.0, le=100.0)
    credits_completed: int = Field(ge=0, le=200)
    failed_courses: int = Field(ge=0, le=30)
    scholarship: str

    attendance_rate: float = Field(ge=0.0, le=100.0)
    lms_logins_per_week: int = Field(ge=0, le=60)
    assignment_submission_rate: float = Field(ge=0.0, le=100.0)
    avg_session_minutes: float = Field(ge=0.0, le=300.0)
    forum_posts: int = Field(ge=0, le=200)
    late_submissions: int = Field(ge=0, le=60)
    advisor_meetings: int = Field(ge=0, le=20)
    financial_default: str

    @field_validator(
        "gender", "region", "family_income_level", "parent_education",
        "major", "scholarship", "financial_default",
    )
    @classmethod
    def _check_category(cls, value: str, info):
        allowed = CATEGORICAL_VALUES[info.field_name]
        cleaned = str(value).strip().lower().replace(" ", "_")
        if cleaned not in allowed:
            raise ValueError(f"قيمة غير مسموح بها للحقل {info.field_name}. المسموح: {allowed}")
        return cleaned


class StudentCreate(StudentBase):
    student_id: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")


class StudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=160)
    age: int | None = Field(default=None, ge=16, le=60)
    gender: str | None = None
    region: str | None = None
    family_income_level: str | None = None
    parent_education: str | None = None
    major: str | None = None
    study_year: int | None = Field(default=None, ge=1, le=6)
    gpa: float | None = Field(default=None, ge=0.0, le=4.0)
    previous_gpa: float | None = Field(default=None, ge=0.0, le=4.0)
    admission_score: float | None = Field(default=None, ge=50.0, le=100.0)
    credits_completed: int | None = Field(default=None, ge=0, le=200)
    failed_courses: int | None = Field(default=None, ge=0, le=30)
    scholarship: str | None = None
    attendance_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    lms_logins_per_week: int | None = Field(default=None, ge=0, le=60)
    assignment_submission_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    avg_session_minutes: float | None = Field(default=None, ge=0.0, le=300.0)
    forum_posts: int | None = Field(default=None, ge=0, le=200)
    late_submissions: int | None = Field(default=None, ge=0, le=60)
    advisor_meetings: int | None = Field(default=None, ge=0, le=20)
    financial_default: str | None = None

    @field_validator(
        "gender", "region", "family_income_level", "parent_education",
        "major", "scholarship", "financial_default",
    )
    @classmethod
    def _check_category(cls, value, info):
        if value is None:
            return value
        allowed = CATEGORICAL_VALUES[info.field_name]
        cleaned = str(value).strip().lower().replace(" ", "_")
        if cleaned not in allowed:
            raise ValueError(f"قيمة غير مسموح بها للحقل {info.field_name}. المسموح: {allowed}")
        return cleaned


class StudentOut(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    last_probability: float | None = None
    last_risk_level: str | None = None
    last_predicted_at: datetime | None = None
    created_at: datetime


class StudentPage(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------------ التنبؤ
class PredictionOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    student_id: str
    model: str
    prediction: int
    prediction_label: str
    probability: float
    risk_level: str
    risk_level_ar: str
    created_at: datetime | None = None


class RecommendationOut(BaseModel):
    code: str
    title_ar: str
    action_ar: str
    category: str
    priority: int
    trigger_ar: str = ""
