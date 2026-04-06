FROM python:3.11-slim

# تثبيت Ghostscript + أدوات النظام الأساسية
RUN apt-get update && \
    apt-get install -y ghostscript && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p uploads compressed

ENV PORT=10000
# استخدام Gunicorn بدل app.run() للإنتاج
CMD exec gunicorn -w 2 -b 0.0.0.0:$PORT app:app --log-file -
