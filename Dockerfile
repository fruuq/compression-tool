FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 
ENV LC_ALL=C.UTF-8

RUN apt-get update && \
    apt-get install -y --no-install-recommends ghostscript && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY . .
RUN mkdir -p uploads compressed

ENV PORT=10000

CMD exec gunicorn -w 2 -b 0.0.0.0:$PORT app:app --log-file -
