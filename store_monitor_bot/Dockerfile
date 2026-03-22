# ======================================================
# Dockerfile - صورة Docker للمشروع
# ======================================================

FROM python:3.11-slim

# مجلد العمل داخل الـ container
WORKDIR /app

# تثبيت المتطلبات النظامية
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً (للـ cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# نسخ باقي الملفات
COPY . .

# إنشاء مجلد اللوغ
RUN mkdir -p logs

# Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# تشغيل البوت
CMD ["python", "main.py"]
