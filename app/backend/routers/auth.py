"""مسارات المصادقة: تسجيل الدخول، الخروج، بيانات الجلسة، تغيير كلمة المرور."""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...config import settings
from ...db.database import get_db
from ...db.models import User
from ...schemas import LoginRequest, PasswordChange, TokenResponse, UserOut
from ...security import (
    PERMISSIONS,
    create_access_token,
    hash_password,
    role_label_ar,
    validate_password_strength,
    verify_password,
)
from ..deps import get_current_user, log_action
from ...utils import utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])

# حماية بسيطة ضد محاولات التخمين المتكررة (في الذاكرة)
_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 8
_WINDOW_SECONDS = 300


def _throttle(key: str) -> None:
    now = time.time()
    _ATTEMPTS[key] = [t for t in _ATTEMPTS[key] if now - t < _WINDOW_SECONDS]
    if len(_ATTEMPTS[key]) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="عدد محاولات الدخول تجاوز الحد المسموح. حاول مرة أخرى بعد بضع دقائق.",
        )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_key = (request.client.host if request.client else "unknown") + "|" + payload.identifier
    _throttle(client_key)

    identifier = payload.identifier.strip()
    user = (
        db.query(User)
        .filter(or_(User.username == identifier, User.email == identifier.lower()))
        .first()
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        _ATTEMPTS[client_key].append(time.time())
        log_action(db, None, "login_failed", "auth", f"identifier={identifier}", level="warning")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب معطّل. يرجى مراجعة مدير النظام.",
        )

    _ATTEMPTS.pop(client_key, None)
    user.last_login_at = utcnow()
    db.commit()

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
    response.set_cookie(
        key="ews_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    log_action(db, user, "login", "auth", f"role={user.role}")

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
        permissions=sorted(PERMISSIONS.get(user.role, set())),
    )


@router.post("/logout")
def logout(response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.delete_cookie("ews_session", path="/")
    log_action(db, user, "logout", "auth")
    return {"detail": "تم تسجيل الخروج بنجاح."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user": UserOut.model_validate(user),
        "role_label_ar": role_label_ar(user.role),
        "permissions": sorted(PERMISSIONS.get(user.role, set())),
    }


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة.")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    log_action(db, user, "change_password", "auth")
    return {"detail": "تم تغيير كلمة المرور بنجاح."}
