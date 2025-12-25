# ============================================================
# OMNI2 Dockerfile
# ============================================================
# Multi-stage build for production-ready container
# ============================================================

# ============================================================
# Stage 1: Base image with Python and uv
# ============================================================
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# ============================================================
# Stage 2: Development image
# ============================================================
FROM base as development

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies (including dev dependencies)
RUN uv pip install --system -e ".[dev]"

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Development startup with hot-reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Stage 3: Production dependencies
# ============================================================
FROM base as prod-deps

# Copy dependency files
COPY pyproject.toml ./

# Install only production dependencies
RUN uv pip install --system .

# ============================================================
# Stage 4: Production image
# ============================================================
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 omni2 && \
    mkdir -p /app /app/logs && \
    chown -R omni2:omni2 /app

# Set working directory
WORKDIR /app

# Copy Python packages from prod-deps stage
COPY --from=prod-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=prod-deps /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=omni2:omni2 . .

# Switch to non-root user
USER omni2

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production startup with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ============================================================
# Build Instructions
# ============================================================
# Development:
#   docker build --target development -t omni2:dev .
#   docker run -p 8000:8000 -v $(pwd):/app omni2:dev
#
# Production:
#   docker build --target production -t omni2:prod .
#   docker run -p 8000:8000 --env-file .env omni2:prod
#
# Using docker-compose (recommended):
#   docker-compose up --build
# ============================================================
