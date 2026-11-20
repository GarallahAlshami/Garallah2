"""نظام التوصيات الإرشادية.

القواعد مخزّنة في جدول recommendations داخل قاعدة البيانات، لذا يمكن للمدير
إضافة أو تعطيل قواعد جديدة مستقبلًا دون تعديل الكود.
كل قاعدة تربط عامل خطر (خاصية) بشرط وقيمة عتبة وتوصية عملية.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Recommendation
from ..ml.features import FEATURE_LABELS_AR, VALUE_LABELS_AR

# القواعد الافتراضية التي تُزرع عند أول تشغيل
DEFAULT_RULES: list[dict] = [
    {
        "code": "LOW_GPA",
        "feature": "gpa",
        "operator": "<",
        "threshold": "2.0",
        "title_ar": "دعم أكاديمي عاجل",
        "action_ar": "إحالة الطالب إلى برنامج الدعم الأكاديمي، وتحديد مقررات التعثر، وجدولة ساعات تقوية أسبوعية مع عضو هيئة تدريس.",
        "category": "academic",
        "priority": 1,
    },
    {
        "code": "MEDIUM_GPA",
        "feature": "gpa",
        "operator": "<",
        "threshold": "2.5",
        "title_ar": "متابعة أكاديمية دورية",
        "action_ar": "مراجعة الخطة الدراسية مع الطالب وتخفيف العبء الدراسي للفصل القادم، مع متابعة شهرية للمعدل.",
        "category": "academic",
        "priority": 2,
    },
    {
        "code": "LOW_ATTENDANCE",
        "feature": "attendance_rate",
        "operator": "<",
        "threshold": "70",
        "title_ar": "متابعة الحضور والتواصل مع الطالب",
        "action_ar": "التواصل المباشر مع الطالب لمعرفة أسباب الغياب، وتفعيل تنبيهات الحضور، وإشعار ولي الأمر عند تجاوز حد الغياب.",
        "category": "attendance",
        "priority": 1,
    },
    {
        "code": "MODERATE_ATTENDANCE",
        "feature": "attendance_rate",
        "operator": "<",
        "threshold": "80",
        "title_ar": "تنبيه مبكر بشأن الحضور",
        "action_ar": "إرسال تنبيه للطالب بأن نسبة حضوره اقتربت من الحد الحرج، مع متابعة أسبوعية.",
        "category": "attendance",
        "priority": 2,
    },
    {
        "code": "LOW_LMS",
        "feature": "lms_logins_per_week",
        "operator": "<",
        "threshold": "3",
        "title_ar": "متابعة النشاط في منصة التعلم الإلكتروني",
        "action_ar": "التحقق من قدرة الطالب على الوصول للمنصة، وتقديم دعم تقني، وتشجيعه على متابعة المحتوى الرقمي أسبوعيًا.",
        "category": "engagement",
        "priority": 1,
    },
    {
        "code": "LOW_SUBMISSION",
        "feature": "assignment_submission_rate",
        "operator": "<",
        "threshold": "70",
        "title_ar": "خطة لرفع نسبة تسليم الواجبات",
        "action_ar": "الاتفاق مع الطالب على جدول زمني للتسليم، وتفعيل تذكيرات آلية قبل موعد كل واجب.",
        "category": "engagement",
        "priority": 2,
    },
    {
        "code": "HIGH_FAILED",
        "feature": "failed_courses",
        "operator": ">",
        "threshold": "3",
        "title_ar": "خطة معالجة المقررات المتعثرة",
        "action_ar": "إعادة جدولة المقررات الراسب فيها على فصول متتابعة، وربط الطالب ببرنامج الإرشاد الأكاديمي المكثف.",
        "category": "academic",
        "priority": 1,
    },
    {
        "code": "HIGH_LATE",
        "feature": "late_submissions",
        "operator": ">",
        "threshold": "8",
        "title_ar": "تدريب على إدارة الوقت",
        "action_ar": "إلحاق الطالب بورشة مهارات إدارة الوقت والتنظيم الدراسي.",
        "category": "engagement",
        "priority": 3,
    },
    {
        "code": "FINANCIAL_DEFAULT",
        "feature": "financial_default",
        "operator": "==",
        "threshold": "yes",
        "title_ar": "دعم مالي وإعادة جدولة الرسوم",
        "action_ar": "إحالة الحالة إلى شؤون الطلاب لدراسة إمكانية تقسيط الرسوم أو منح إعفاء جزئي.",
        "category": "financial",
        "priority": 1,
    },
    {
        "code": "LOW_INCOME",
        "feature": "family_income_level",
        "operator": "==",
        "threshold": "low",
        "title_ar": "بحث فرص الدعم والمنح",
        "action_ar": "ترشيح الطالب لبرامج المنح الداخلية أو فرص العمل الطلابي داخل الجامعة.",
        "category": "financial",
        "priority": 3,
    },
    {
        "code": "NO_ADVISOR_MEETINGS",
        "feature": "advisor_meetings",
        "operator": "<",
        "threshold": "1",
        "title_ar": "تفعيل الإرشاد الأكاديمي",
        "action_ar": "تحديد موعد لقاء إرشادي فوري مع المرشد الأكاديمي وتوثيق خطة متابعة فصلية.",
        "category": "advising",
        "priority": 2,
    },
    {
        "code": "LOW_SESSION_TIME",
        "feature": "avg_session_minutes",
        "operator": "<",
        "threshold": "15",
        "title_ar": "رفع زمن التفاعل مع المحتوى الرقمي",
        "action_ar": "توجيه الطالب لمصادر تعليمية قصيرة ومتدرجة لرفع زمن التفاعل الأسبوعي مع المنصة.",
        "category": "engagement",
        "priority": 3,
    },
]

CATEGORY_LABELS_AR = {
    "academic": "أكاديمي",
    "attendance": "الحضور",
    "engagement": "التفاعل الإلكتروني",
    "financial": "مالي",
    "advising": "إرشادي",
}


def seed_recommendations(db: Session) -> int:
    """زرع القواعد الافتراضية إن لم تكن موجودة. يعيد عدد القواعد المضافة."""
    existing = {row[0] for row in db.query(Recommendation.code).all()}
    added = 0
    for rule in DEFAULT_RULES:
        if rule["code"] in existing:
            continue
        db.add(Recommendation(**rule, is_active=True))
        added += 1
    if added:
        db.commit()
    return added


def _matches(rule: Recommendation, value) -> bool:
    if value is None:
        return False
    try:
        if rule.operator == "==":
            return str(value).strip().lower() == str(rule.threshold).strip().lower()
        numeric = float(value)
        threshold = float(rule.threshold)
        if rule.operator == "<":
            return numeric < threshold
        if rule.operator == ">":
            return numeric > threshold
        if rule.operator == "<=":
            return numeric <= threshold
        if rule.operator == ">=":
            return numeric >= threshold
    except (TypeError, ValueError):
        return False
    return False


def _trigger_text(rule: Recommendation, value) -> str:
    label = FEATURE_LABELS_AR.get(rule.feature, rule.feature)
    shown = VALUE_LABELS_AR.get(str(value), str(value))
    symbol = {"<": "أقل من", ">": "أكبر من", "==": "يساوي", "<=": "لا يتجاوز", ">=": "لا يقل عن"}
    threshold = VALUE_LABELS_AR.get(rule.threshold, rule.threshold)
    return f"{label} = {shown} ({symbol.get(rule.operator, rule.operator)} {threshold})"


def build_recommendations(
    db: Session, student_data: dict, risk_level: str = "medium", limit: int = 8
) -> list[dict]:
    """توليد توصيات مرتبطة بعوامل الخطر الفعلية لبيانات الطالب."""
    rules = (
        db.query(Recommendation)
        .filter(Recommendation.is_active.is_(True))
        .order_by(Recommendation.priority.asc())
        .all()
    )
    results: list[dict] = []
    seen_features: set[str] = set()

    for rule in rules:
        value = student_data.get(rule.feature)
        if not _matches(rule, value):
            continue
        # تجنّب تكرار توصيتين لنفس العامل (تُعتمد الأعلى أولوية)
        if rule.feature in seen_features:
            continue
        seen_features.add(rule.feature)
        results.append(
            {
                "code": rule.code,
                "title_ar": rule.title_ar,
                "action_ar": rule.action_ar,
                "category": rule.category,
                "category_ar": CATEGORY_LABELS_AR.get(rule.category, rule.category),
                "priority": rule.priority,
                "trigger_ar": _trigger_text(rule, value),
            }
        )

    if not results:
        results.append(
            {
                "code": "STABLE",
                "title_ar": "لا توجد عوامل خطر جوهرية",
                "action_ar": "الاستمرار في المتابعة الدورية العادية وتشجيع الطالب على الحفاظ على مستواه.",
                "category": "advising",
                "category_ar": CATEGORY_LABELS_AR["advising"],
                "priority": 3,
                "trigger_ar": "جميع المؤشرات ضمن النطاق الآمن",
            }
        )

    if risk_level == "high":
        results.insert(
            0,
            {
                "code": "HIGH_RISK_ESCALATION",
                "title_ar": "تصعيد الحالة إلى لجنة الإرشاد",
                "action_ar": "رفع الحالة إلى لجنة الإرشاد الأكاديمي خلال أسبوع، وإعداد خطة تدخل فردية موثقة مع مؤشرات متابعة.",
                "category": "advising",
                "category_ar": CATEGORY_LABELS_AR["advising"],
                "priority": 1,
                "trigger_ar": "مستوى الخطورة: مرتفع",
            },
        )

    return sorted(results, key=lambda r: r["priority"])[:limit]
