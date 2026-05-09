FROM python:3.12-slim

WORKDIR /app

# Install lxml/pdfplumber system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# State directory (Railway-managed Volume mounts here at runtime; no Dockerfile VOLUME)
ENV DATA_DIR=/data

# Railway sets PORT
ENV PORT=8080
ENV BIND_HOST=0.0.0.0
EXPOSE 8080

# Single-process: APScheduler + HTTP server
CMD ["python", "-u", "entrypoint.py"]
