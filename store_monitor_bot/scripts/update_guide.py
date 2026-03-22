"""Update/validate SYSTEM_GUIDE.md sections for newly added dashboard modules."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "SYSTEM_GUIDE.md"

REQUIRED_SECTIONS = [
    "منشئ قائمة البوت",
    "محلل المعرفات",
    "إدارة المجموعات",
]


def main() -> int:
    if not GUIDE.exists():
        raise FileNotFoundError(f"Missing guide file: {GUIDE}")

    content = GUIDE.read_text(encoding="utf-8", errors="ignore")
    missing = [section for section in REQUIRED_SECTIONS if section not in content]

    if missing:
        appendix = [
            "\n\n════════════════════════════════════════",
            "تحديث تلقائي: ميزات لوحة الإدارة الجديدة",
            "════════════════════════════════════════",
            "تمت إضافة الميزات التالية في النظام:",
            "  • منشئ قائمة البوت",
            "  • محلل المعرفات",
            "  • إدارة المجموعات",
        ]
        GUIDE.write_text(content + "\n" + "\n".join(appendix) + "\n", encoding="utf-8")
        print("Guide updated with missing sections:", ", ".join(missing))
    else:
        print("Guide already up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
