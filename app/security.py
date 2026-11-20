"""طبقة الأمان: تجزئة كلمات المرور، إصدار الرموز (JWT)، والتحقق من الصلاحيات."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any

from .config import settings

ROLES = ("admin", "advisor")
ROLE_LABELS_AR = {"admin": "مدير النظام", "advisor": "مرشد أكاديمي"}

_PASSWORD_POLICY = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")
_USERNAME_POLICY = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
_EMAIL_POLICY = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ----------------------------------------------------------- كلمات المرور
def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 مع ملح عشوائي لكل مستخدم."""
    salt = secrets.token_bytes(16)
    iterations = settings.PASSWORD_ITERATIONS
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, hash_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> None:
    if not _PASSWORD_POLICY.match(password or ""):
        raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل وتحتوي على حرف ورقم.")


def validate_username(username: str) -> None:
    if not _USERNAME_POLICY.match(username or ""):
        raise ValueError("اسم المستخدم يجب أن يكون 3-64 حرفًا لاتينيًا/رقمًا بدون مسافات.")


def validate_email(email: str) -> None:
    if not _EMAIL_POLICY.match(email or ""):
        raise ValueError("صيغة البريد الإلكتروني غير صحيحة.")


# ------------------------------------------------------------------- JWT
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class TokenError(Exception):
    """رمز غير صالح أو منتهي الصلاحية."""


def create_access_token(payload: dict[str, Any], expires_minutes: int | None = None) -> str:
    """إصدار رمز وصول موقّع (HS256)."""
    expires_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = int(time.time())
    body = {
        **payload,
        "iat": now,
        "exp": now + expires_minutes * 60,
        "jti": secrets.token_hex(8),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()),
    ]
    signing_input = ".".join(segments).encode()
    signature = hmac.new(settings.SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url(signature))
    return ".".join(segments)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("رمز الجلسة غير صالح.") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(settings.SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        raise TokenError("توقيع رمز الجلسة غير صحيح.")

    payload = json.loads(_b64url_decode(payload_b64))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("انتهت صلاحية الجلسة، يرجى تسجيل الدخول مرة أخرى.")
    return payload


# ------------------------------------------------------------- الصلاحيات
PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "dashboard:view", "students:view", "students:manage",
        "predict:run", "explain:view", "batch:run",
        "reports:view", "reports:create", "models:view",
        "users:view", "users:manage", "logs:view",
    },
    "advisor": {
        "dashboard:view", "students:view", "students:manage",
        "predict:run", "explain:view", "batch:run",
        "reports:view", "reports:create", "models:view",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def role_label_ar(role: str) -> str:
    return ROLE_LABELS_AR.get(role, role)
