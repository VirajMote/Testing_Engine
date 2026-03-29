# Dockerfile — Railway deployment for receipt-processor
FROM python:3.11-slim

# Install system dependencies
# tesseract-ocr: OCR engine
# poppler-utils: PDF → image conversion (pdf2image)
# libgl1 + libglib2.0-0: required by opencv-python-headless
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        libgl1 \
        libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (layer caching — only rebuilds if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway injects $PORT at runtime — uvicorn must bind to it
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
