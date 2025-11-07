# Kirby Collector - Production Dockerfile
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    pkg-config \
    libsecp256k1-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code (needed for pyproject.toml install)
COPY . .

# Install Python dependencies from pyproject.toml
# Use non-editable install for production
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN useradd -m -u 1000 kirby && \
    chown -R kirby:kirby /app

USER kirby

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "src.collectors.main"]
