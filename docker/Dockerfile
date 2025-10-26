# Multi-stage Dockerfile for Kirby
# Stage 1: Base image with dependencies
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# Stage 2: Development image
FROM base as development

# Install development dependencies
RUN pip install -e ".[dev]"

# Copy application code
COPY . .

# Default command for development
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production API image
FROM base as api

# Copy application code
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 kirby && \
    chown -R kirby:kirby /app

USER kirby

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["gunicorn", "src.api.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# Stage 4: Production Collector image
FROM base as collector

# Copy application code
COPY src ./src
COPY config ./config

# Create non-root user
RUN useradd -m -u 1000 kirby && \
    chown -R kirby:kirby /app

USER kirby

# Default command
CMD ["python", "-m", "src.collectors.main"]
