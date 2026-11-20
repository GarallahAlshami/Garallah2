"""إعدادات النظام — تُقرأ من متغيرات البيئة أو من ملف .env"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """قارئ بسيط لملف .env بدون الاعتماد على مكتبة خارجية."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Settings:
    APP_NAME: str = "نظام إنذار مبكر ذكي للحد من تسرب الطالب في التعليم العالي"
    APP_NAME_EN: str = "Smart Early Warning System for Student Dropout Prevention"
    VERSION: str = "1.0.0"

    # الأمان — لا توجد أي أسرار مكتوبة داخل الكود؛ تُولَّد عشوائيًا إن لم تُضبط
    SECRET_KEY: str = _env("EWS_SECRET_KEY", secrets.token_urlsafe(48))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(_env("EWS_TOKEN_EXPIRE_MINUTES", "480"))
    PASSWORD_ITERATIONS: int = int(_env("EWS_PASSWORD_ITERATIONS", "200000"))

    # المسارات
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    MODELS_DIR: Path = BASE_DIR / "models"
    DATABASE_DIR: Path = BASE_DIR / "database"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    FRONTEND_DIR: Path = BASE_DIR / "app" / "frontend"

    DATASET_PATH: Path = Path(_env("EWS_DATASET_PATH", str(BASE_DIR / "data" / "students_dataset.csv")))

    # قاعدة البيانات — SQLite افتراضيًا، وقابلة للتحويل إلى MySQL/PostgreSQL
    DATABASE_URL: str = _env("EWS_DATABASE_URL", f"sqlite:///{BASE_DIR / 'database' / 'ews.db'}")

    # حدود رفع الملفات
    MAX_UPLOAD_MB: int = int(_env("EWS_MAX_UPLOAD_MB", "10"))
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".csv",)

    # عتبات تصنيف الخطورة (احتمال التسرب)
    RISK_MEDIUM_THRESHOLD: float = float(_env("EWS_RISK_MEDIUM", "0.40"))
    RISK_HIGH_THRESHOLD: float = float(_env("EWS_RISK_HIGH", "0.70"))

    # حساب المدير الافتراضي (للتشغيل الأول فقط — يجب تغييره)
    DEFAULT_ADMIN_USERNAME: str = _env("EWS_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_EMAIL: str = _env("EWS_ADMIN_EMAIL", "admin@ews.local")
    DEFAULT_ADMIN_PASSWORD: str = _env("EWS_ADMIN_PASSWORD", secrets.token_urlsafe(32))
    DEFAULT_ADVISOR_USERNAME: str = _env("EWS_ADVISOR_USERNAME", "advisor")
    DEFAULT_ADVISOR_EMAIL: str = _env("EWS_ADVISOR_EMAIL", "advisor@ews.local")
    DEFAULT_ADVISOR_PASSWORD: str = _env("EWS_ADVISOR_PASSWORD", secrets.token_urlsafe(32))


settings = Settings()

for _d in (settings.DATA_DIR, settings.MODELS_DIR, settings.DATABASE_DIR, settings.REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
