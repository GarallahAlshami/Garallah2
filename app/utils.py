"""أدوات مساعدة عامة مشتركة بين وحدات النظام."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """التوقيت العالمي الحالي بدون معلومة المنطقة (naive UTC).

    تُستخدم بديلًا عن `datetime.utcnow()` المهملة في إصدارات بايثون الحديثة،
    مع الحفاظ على نفس الشكل المخزَّن في قاعدة البيانات.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
