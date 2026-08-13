FROM python:3.11-slim

# System dependencies for PyMuPDF and other tools
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dev/test dependencies (pytest suite used by CI and local verification)
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code
COPY . .

# Run as non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser
