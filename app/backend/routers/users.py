"""إدارة المستخدمين والصلاحيات وسجل النظام (خاص بالمدير)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import SystemLog, User
from ...schemas import UserCreate, UserOut, UserUpdate
from ...security import (
    PERMISSIONS,
    ROLE_LABELS_AR,
    hash_password,
    validate_password_strength,
    validate_username,
)
from ..deps import log_action, require_permission
from ...utils import utcnow

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/roles")
def roles(_: User = Depends(require_permission("users:view"))):
    return {
        "roles": [
            {
                "value": role,
                "label": ROLE_LABELS_AR[role],
                "permissions": sorted(perms),
            }
            for role, perms in PERMISSIONS.items()
        ]
    }


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:view")),
    search: str = Query("", max_length=120),
):
    query = db.query(User)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(User.username.ilike(pattern), User.email.ilike(pattern), User.full_name.ilike(pattern))
        )
    return [UserOut.model_validate(u) for u in query.order_by(User.id).all()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
):
    try:
        validate_username(payload.username)
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    exists = (
        db.query(User)
        .filter(or_(User.username == payload.username, User.email == payload.email.lower()))
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="اسم المستخدم أو البريد الإلكتروني مستخدم بالفعل.")

    user = User(
        username=payload.username,
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, admin, "user_create", "users", f"{user.username} role={user.role}")
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث.")

    if "password" in updates:
        try:
            validate_password_strength(updates["password"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        user.password_hash = hash_password(updates.pop("password"))

    if "email" in updates:
        email = updates["email"].lower()
        clash = db.query(User).filter(User.email == email, User.id != user_id).first()
        if clash:
            raise HTTPException(status_code=409, detail="البريد الإلكتروني مستخدم بالفعل.")
        updates["email"] = email

    if user.id == admin.id and updates.get("is_active") is False:
        raise HTTPException(status_code=400, detail="لا يمكنك تعطيل حسابك الحالي.")
    if user.id == admin.id and updates.get("role") not in (None, "admin"):
        raise HTTPException(status_code=400, detail="لا يمكنك تغيير دور حسابك الحالي.")

    for key, value in updates.items():
        setattr(user, key, value)
    user.updated_at = utcnow()
    db.commit()
    db.refresh(user)
    log_action(db, admin, "user_update", "users", f"{user.username}: {list(updates)}")
    return UserOut.model_validate(user)


@router.post("/{user_id}/toggle-active", response_model=UserOut)
def toggle_active(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="لا يمكنك تعطيل حسابك الحالي.")

    active_admins = (
        db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
    )
    if user.role == "admin" and user.is_active and active_admins <= 1:
        raise HTTPException(status_code=400, detail="لا يمكن تعطيل آخر حساب مدير نشط.")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    log_action(
        db, admin, "user_toggle_active", "users",
        f"{user.username} -> {'مفعّل' if user.is_active else 'معطّل'}", level="warning",
    )
    return UserOut.model_validate(user)


@router.get("/logs")
def system_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("logs:view")),
    limit: int = Query(100, ge=1, le=1000),
    action: str = Query("", max_length=64),
):
    query = db.query(SystemLog)
    if action:
        query = query.filter(SystemLog.action == action)
    rows = query.order_by(SystemLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "action": r.action,
            "entity": r.entity,
            "details": r.details,
            "level": r.level,
            "created_at": r.created_at,
        }
        for r in rows
    ]
