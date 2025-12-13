# syntax=docker/dockerfile:1

# =============================================================================
# Base Stage - Common setup for all environments
# =============================================================================
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (same UID as host for file permissions)
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Set working directory and ownership
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root user for all subsequent operations
USER appuser

# Set environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# =============================================================================
# Development Stage - Hot reload, full tooling
# =============================================================================
FROM base AS development

# Copy dependency files (as appuser)
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install dependencies from lockfile (including docs group for MkDocs)
RUN uv sync --frozen --all-groups

# Copy application code (as appuser)
COPY --chown=appuser:appuser . .

# Development command - Run migrations then start with reload
CMD ["sh", "-c", "echo 'Running Alembic migrations...' && uv run alembic upgrade head && echo 'Development server starting...' && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"]

# =============================================================================
# Builder Stage - Production dependency installation
# =============================================================================
FROM base AS builder

# Copy dependency files
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install production dependencies only (no dev dependencies)
RUN uv sync --frozen --no-dev

# =============================================================================
# Production Stage - Minimal runtime
# =============================================================================
FROM python:3.13-slim AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder (as appuser)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code (as appuser)
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f https://localhost:8000/health --insecure || exit 1

# Production command
# TODO F0.4: Re-enable automatic migrations once Alembic is initialized
# NOTE: Remove --ssl-certfile/--ssl-keyfile (Traefik handles SSL termination)
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port 8000"]
