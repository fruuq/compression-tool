# Dockerfile
FROM python:3.11-slim

# تثبيت dependencies المطلوبة لـ Pillow
RUN apt-get update && apt-get install -y libjpeg-dev zlib1g-dev libpng-dev && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد المشروع
WORKDIR /app

# نسخ الملفات
COPY . /app

# تثبيت بايثون requirements
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y ghostscript
# فتح المنفذ 5000
EXPOSE 5000

# أمر التشغيل
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]