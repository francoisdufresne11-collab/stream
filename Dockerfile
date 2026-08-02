FROM python:3.11-slim

# libgl1-mesa-glx renomme en libgl1 sur Debian trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p streams uploads static/sounds

ENV PORT=10000
EXPOSE 10000

# FIX: app:app au lieu de wsgi:app
# gunicorn charge directement le module app.py et utilise la variable app
CMD gunicorn -w 1 --threads 100 -b 0.0.0.0:$PORT --timeout 300 --keep-alive 75 --log-level info --access-logfile - --error-logfile - app:app
