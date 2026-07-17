# Production Dockerfile for AuraSound 2032
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/get/lists/*

WORKDIR /app

# Copy requirement list & install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure upload & storage directories exist
RUN mkdir -p web/uploads/avatars web/uploads/banners

EXPOSE 8000

ENV PORT=8000
CMD ["python", "server.py"]
