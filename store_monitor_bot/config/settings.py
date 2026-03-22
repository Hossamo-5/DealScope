"""
ملف الإعدادات الرئيسي للبوت
============================
هنا تضع جميع مفاتيح API والإعدادات العامة للمشروع
لا تشارك هذا الملف مع أحد - يحتوي على مفاتيح سرية
"""

import os
try:
    from dotenv import load_dotenv
    # تحميل متغيرات البيئة من ملف .env إن وُجد
    load_dotenv()
except Exception:
    # dotenv is optional in some environments (tests, CI).
    pass

# ======================================================
# 🔑 مفاتيح API - اضف مفاتيحك هنا
# ======================================================

# مفتاح بوت تيليغرام - احصل عليه من @BotFather على تيليغرام
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

# معرف مجموعة أو قناة الإدارة الخاصة (رقم سالب للمجموعات)
# مثال: -1001234567890
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1001234567890"))

# قائمة معرفات المديرين (أرقام Telegram User ID)
# يمكن معرفة الـ ID من بوت @userinfobot
ADMIN_USER_IDS = [
    int(x) for x in os.getenv("ADMIN_USER_IDS", "123456789").split(",")
]

# ======================================================
# 🗄️ إعدادات قاعدة البيانات PostgreSQL
# ======================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/store_monitor"
)

# ======================================================
# ⚡ إعدادات Redis (للـ Queue والـ Cache)
# ======================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ======================================================
# 🛍️ إعدادات المراقبة والسكرابينج
# ======================================================

# LongCat AI API for intelligent scraping
LONGCAT_API_KEY = os.getenv(
    "LONGCAT_API_KEY",
    "PUT_YOUR_LONGCAT_API_KEY_HERE"
)
LONGCAT_BASE_URL = "https://api.longcat.chat/openai"
LONGCAT_MODEL = "LongCat-Flash-Chat"

# AI scraping settings
AI_SCRAPING_ENABLED = os.getenv(
    "AI_SCRAPING_ENABLED", "true"
).lower() == "true"

# Use AI as fallback or primary
# "fallback" = try CSS first, AI if fails
# "primary"  = AI first, CSS as backup
AI_SCRAPING_MODE = os.getenv(
    "AI_SCRAPING_MODE", "fallback"
)

# تأخير بين كل طلب وآخر (بالثواني) - مهم لتجنب الحظر
SCRAPING_DELAY_SECONDS = 2

# أقصى عدد طلبات في الدقيقة لكل موقع
MAX_REQUESTS_PER_MINUTE = 10

# عدد مرات إعادة المحاولة عند الفشل
MAX_RETRY_ATTEMPTS = 3

# الانتظار قبل إعادة المحاولة (بالثواني)
RETRY_DELAY_SECONDS = 5

# ======================================================
# ⏰ جداول الفحص حسب الخطة
# ======================================================

# كم دقيقة بين كل فحص وآخر حسب نوع الاشتراك
SCAN_INTERVALS = {
    "free": 60,          # مجانية: كل 60 دقيقة
    "basic": 30,         # أساسية: كل 30 دقيقة
    "professional": 15,  # احترافية: كل 15 دقيقة
}

# فحص الفئات (أبطأ من المنتجات الفردية)
CATEGORY_SCAN_INTERVAL = 120  # كل ساعتين

# فحص المتاجر الكاملة
STORE_SCAN_INTERVAL = 180  # كل 3 ساعات

# ======================================================
# 💳 حدود الخطط
# ======================================================

PLAN_LIMITS = {
    "free": {
        "max_products": 3,
        "max_categories": 0,
        "max_stores": 0,
        "price": 0,
        "scan_interval": 60,
    },
    "basic": {
        "max_products": 50,
        "max_categories": 10,
        "max_stores": 0,
        "price": 10,  # ريال سعودي
        "scan_interval": 30,
    },
    "professional": {
        "max_products": 300,
        "max_categories": 50,
        "max_stores": 20,
        "price": 49,  # ريال سعودي
        "scan_interval": 15,
    },
}

# ======================================================
# 📊 إعدادات تقييم الفرص (Opportunity Score)
# ======================================================

# الحد الأدنى لنسبة الخصم لاعتبار المنتج فرصة
MIN_DISCOUNT_PERCENT = 10

# أوزان حساب نقاط الفرصة (المجموع = 100)
SCORE_WEIGHTS = {
    "discount_percent": 40,    # نسبة الخصم (الأهم)
    "product_rating": 20,      # تقييم المنتج
    "review_count": 15,        # عدد المراجعات
    "stock_availability": 10,  # توافر المخزون
    "price_history_low": 15,   # هل هو أقل سعر تاريخي؟
}

# تصنيف الفرص بناءً على النقاط
SCORE_LEVELS = {
    "excellent": 90,   # 90+ = ممتاز 🔥
    "good": 70,        # 70-89 = جيد ✅
    "normal": 0,       # أقل من 70 = عادي ℹ️
}

# ======================================================
# 🌐 إعدادات الـ Admin Dashboard
# ======================================================
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))

# مفتاح سري لتشفير الجلسات في الداشبورد
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY_IN_PRODUCTION")

# ======================================================
# 📝 إعدادات اللوغ (Logging)
# ======================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "logs/bot.log"
