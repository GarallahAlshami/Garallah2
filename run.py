"""مشغّل النظام — نقطة التشغيل الموحّدة.

الاستخدام:
    python run.py                 # تشغيل الخادم على المنفذ 8000
    python run.py --port 9000     # منفذ مخصّص
    python run.py --setup         # توليد البيانات + تدريب النموذج + تهيئة القاعدة ثم التشغيل
    python run.py --reload        # وضع التطوير مع إعادة التحميل التلقائي
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _run(description: str, args: list[str]) -> None:
    print(f"\n>>> {description}")
    result = subprocess.run([sys.executable, *args], cwd=str(ROOT))
    if result.returncode != 0:
        print(f"!!! فشلت الخطوة: {description}")
        sys.exit(result.returncode)


def setup() -> None:
    """تجهيز كامل: البيانات ← النموذج ← قاعدة البيانات."""
    dataset = ROOT / "data" / "students_dataset.csv"
    if not dataset.exists():
        _run("توليد مجموعة البيانات التجريبية", ["scripts/generate_dataset.py"])
    else:
        print(f">>> مجموعة البيانات موجودة مسبقًا: {dataset.name}")

    if not (ROOT / "models" / "xgboost_pipeline.joblib").exists():
        _run("تدريب النماذج (Logistic Regression + XGBoost)", ["-m", "app.ml.train"])
    else:
        print(">>> النماذج مدرَّبة مسبقًا.")

    _run("تهيئة قاعدة البيانات وإدخال البيانات الأولية", ["-m", "app.db.seed"])


def main() -> None:
    parser = argparse.ArgumentParser(description="نظام إنذار مبكر ذكي للحد من تسرب الطالب")
    parser.add_argument("--host", default="127.0.0.1", help="عنوان الاستماع (افتراضي 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="المنفذ (افتراضي 8000)")
    parser.add_argument("--reload", action="store_true", help="إعادة التحميل التلقائي (وضع التطوير)")
    parser.add_argument("--setup", action="store_true", help="تجهيز البيانات والنموذج والقاعدة قبل التشغيل")
    parser.add_argument("--setup-only", action="store_true", help="تنفيذ التجهيز فقط دون تشغيل الخادم")
    args = parser.parse_args()

    if args.setup or args.setup_only:
        setup()
    if args.setup_only:
        return

    import uvicorn

    print("\n" + "=" * 62)
    print("  نظام إنذار مبكر ذكي للحد من تسرب الطالب")
    print(f"  الواجهة:      http://{args.host}:{args.port}/")
    print(f"  توثيق الـAPI: http://{args.host}:{args.port}/api/docs")
    print("  للإيقاف: Ctrl + C")
    print("=" * 62 + "\n")

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
