# Production Multi-Stage Dockerfile for FinnAI FastAPI Backend
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Set Python environment variables for performance and clean logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install required system packages for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code & config files
COPY . .

# Expose Render default / configurable PORT (defaults to 8000 locally)
EXPOSE 8000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT for Render deployment
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
