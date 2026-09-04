# AI-Powered HOTS Question Generator - Backend Container
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including Tesseract OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy backend dependency list
COPY backend/requirements.txt /app/backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY . /app

# Set PYTHONPATH to backend
ENV PYTHONPATH=/app/backend

# Expose default API port
EXPOSE 8000

# Default command placeholder (will execute FastAPI app when implemented)
CMD ["python", "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
