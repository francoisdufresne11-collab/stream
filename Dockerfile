FROM python:3.11-slim

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

# gthread = worker threading, compatible Flask-SocketIO async_mode=threading
# -w 1 obligatoire (memoire partagee)
# --threads 100 = 100 connexions simultanees
# --timeout 120 = evite que gunicorn kill les longues connexions Socket.IO
CMD gunicorn \
    --worker-class gthread \
    --workers 1 \
    --threads 100 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:app
