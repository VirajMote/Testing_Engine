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
 
# start.py reads $PORT at runtime — avoids shell variable expansion issues on Railway
CMD ["python", "start.py"]