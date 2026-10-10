FROM python:3.10-slim

# System dependencies for OpenCV video decoding
# ffmpeg is REQUIRED — it's what actually decodes MP4/MOV/AVI/MKV
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .

# Create a writable temp dir (in case /tmp is restricted)
RUN mkdir -p /tmp/frames && chmod 777 /tmp/frames

EXPOSE 8000

# Production WSGI server with a long timeout for video processing
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]