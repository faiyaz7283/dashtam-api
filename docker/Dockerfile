# syntax=docker/dockerfile:1

# We use the UV Python image which includes both UV and Python
# This is more efficient than copying UV from a distroless image
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Set environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================
# Development stage - includes all dev tools
# ============================================
FROM base AS development

# Initialize project if not exists, otherwise sync existing
COPY pyproject.toml* uv.lock* ./
COPY requirements*.txt ./

# Initialize project if pyproject.toml doesn't exist
RUN if [ ! -f "pyproject.toml" ]; then \
        uv init --app --name dashtam --python 3.13 --no-readme; \
    fi

# Add all dependencies from requirements files
RUN uv add --requirements requirements.txt && \
    uv add --dev --requirements requirements-dev.txt

# Copy application code
COPY . .

# Ensure virtual environment is created
RUN uv sync

# Development command - run migrations then start with reload
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"]

# ============================================
# Builder stage - prepares production deps
# ============================================
FROM base AS builder

# Copy project files
COPY pyproject.toml* uv.lock* ./
COPY requirements.txt ./

# Initialize project if needed
RUN if [ ! -f "pyproject.toml" ]; then \
        uv init --app --name dashtam --python 3.13 --no-readme --author-from none; \
    fi

# Add production dependencies only
RUN uv add --requirements requirements.txt

# Create virtual environment with dependencies
RUN uv sync --no-dev

# ============================================
# Production stage - minimal runtime
# ============================================
FROM python:3.13-slim AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f https://localhost:8000/health --insecure || exit 1

# Production command - run migrations then start (no reload)
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"]

# ============================================
# Callback server stage
# ============================================
FROM python:3.13-slim AS callback

# Set environment for unbuffered output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install required Python packages
RUN pip install --no-cache-dir requests urllib3

WORKDIR /app

# Copy callback server
COPY callback_server.py ./

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Run callback server with unbuffered output
CMD ["python", "-u", "callback_server.py"]
