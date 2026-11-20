"""اتصال قاعدة البيانات (SQLAlchemy).

الافتراضي SQLite للنسخة المحلية. المخطط مصمم بأنواع قياسية قابلة للانتقال إلى
MySQL أو PostgreSQL بتغيير المتغير EWS_DATABASE_URL فقط.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """تبعية FastAPI لإدارة دورة حياة الجلسة."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """إنشاء كل الجداول إن لم تكن موجودة."""
    from . import models  # noqa: F401  (لتسجيل النماذج)

    Base.metadata.create_all(bind=engine)
