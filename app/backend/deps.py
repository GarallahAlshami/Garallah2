"""التبعيات المشتركة: استخراج المستخدم الحالي والتحقق من الصلاحيات."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import SystemLog, User
from ..security import TokenError, decode_access_token, has_permission

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="غير مصرح لك — يرجى تسجيل الدخول.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get("ews_session")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
    if user is None:
        raise CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="الحساب معطّل.")
    return user


def require_permission(permission: str):
    """مولّد تبعية تتحقق من امتلاك المستخدم لصلاحية محددة."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ليست لديك صلاحية للوصول إلى هذه الوظيفة.",
            )
        return user

    return _checker


def log_action(
    db: Session, user: User | None, action: str, entity: str = "", details: str = "",
    level: str = "info",
) -> None:
    """تسجيل عملية في سجل النظام."""
    db.add(
        SystemLog(
            user_id=user.id if user else None,
            username=user.username if user else "-",
            action=action,
            entity=entity,
            details=details[:2000],
            level=level,
        )
    )
    db.commit()
