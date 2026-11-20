"""نقطة تشغيل النظام (FastAPI).

المعمارية:
    Frontend (HTML/CSS/JS)  →  Backend API (FastAPI)  →  ML Service  →  Database (SQLite)

التشغيل:
    uvicorn app.main:app --reload
أو:
    python run.py
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .backend.routers import (
    auth,
    batch,
    dashboard,
    explain,
    models,
    predictions,
    reports,
    students,
    users,
)
from .config import settings
from .db.database import init_db
from .ml.predict import is_model_available

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("ews")

app = FastAPI(
    title=settings.APP_NAME_EN,
    description=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    """رسائل تحقق عربية مفهومة بدلًا من مخرجات Pydantic الخام."""
    details = []
    for error in exc.errors():
        location = " → ".join(str(p) for p in error.get("loc", []) if p not in ("body", "query"))
        details.append(f"{location}: {error.get('msg', '')}")
    return JSONResponse(
        status_code=422,
        content={"detail": "بيانات غير صالحة. " + " | ".join(details[:6])},
    )


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("قاعدة البيانات جاهزة: %s", settings.DATABASE_URL)
    if is_model_available("xgboost"):
        logger.info("نموذج XGBoost محمّل وجاهز للتنبؤ.")
    else:
        logger.warning("النموذج غير مدرَّب. نفّذ الأمر: python -m app.ml.train")


# ------------------------------------------------------------------ المسارات
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(students.router)
app.include_router(predictions.router)
app.include_router(explain.router)
app.include_router(batch.router)
app.include_router(models.router)
app.include_router(reports.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "model_ready": is_model_available("xgboost"),
    }


# ----------------------------------------------------------------- الواجهة
STATIC_DIR = settings.FRONTEND_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def login_page():
    return FileResponse(settings.FRONTEND_DIR / "index.html")


@app.get("/app", include_in_schema=False)
def app_page():
    return FileResponse(settings.FRONTEND_DIR / "app.html")
