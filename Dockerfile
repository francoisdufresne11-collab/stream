FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p streams static/sounds

ENV PORT=10000
EXPOSE 10000

# gthread = worker threading natif Python
# AUCUNE dependance C/Cython (pas gevent, pas eventlet)
# Compatible Python 3.8 -> 3.14+
CMD ["gunicorn",\
     "--worker-class","gthread",\
     "--workers","1",\
     "--threads","100",\
     "--bind","0.0.0.0:10000",\
     "--timeout","120",\
     "--keep-alive","5",\
     "--log-level","info",\
     "--access-logfile","-",\
     "--error-logfile","-",\
     "app:app"]
