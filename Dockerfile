FROM python:3.11-slim

# FIX: libgl1-mesa-glx supprime sur Debian trixie -> utiliser libgl1
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

CMD gunicorn -w 1 --threads 100 -b 0.0.0.0:$PORT --timeout 300 --keep-alive 75 --log-level info --access-logfile - --error-logfile - wsgi:app
