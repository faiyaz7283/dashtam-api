# Docker & Build Infrastructure Refactoring Plan

**Date:** 2025-10-05  
**Status:** Ready for Implementation  
**Priority:** High  
**Estimated Time:** 4-6 hours

---

## Overview

This document provides the complete implementation plan for refactoring the Docker and build infrastructure based on the audit findings. The refactoring addresses critical security, maintainability, and development workflow issues.

---

## Current State vs. Target State

### Current State ❌

```bash
Dashtam/
├── docker/Dockerfile              # Creates pyproject.toml dynamically, runs as root
├── docker-compose.yml             # Unused, has wrong .env mounting
├── docker-compose.dev.yml         # Actually used, hardcodes env vars
├── docker-compose.test.yml        # Actually used, hardcodes env vars
├── docker-compose.ci.yml          # Used in GitHub Actions
├── requirements.txt               # Old-style dependencies
├── requirements-dev.txt           # Old-style dev dependencies
├── pyproject.toml                 # ✅ NOW EXISTS (extracted from container)
└── uv.lock                        # ✅ NOW EXISTS (extracted from container)
```

**Problems:**

- 🔴 No non-root user in dev/test
- 🔴 Base docker-compose.yml unused and incorrect
- 🔴 Environment variables hardcoded in compose files
- 🟡 Dockerfile creates pyproject.toml dynamically
- 🟡 requirements.txt still primary source

### Target State ✅

```bash
Dashtam/
├── docker/
│   ├── Dockerfile                # ✅ Reusable, non-root user, uses pyproject.toml
│   └── .dockerignore             # ✅ Optimize build context
├── compose/
│   ├── docker-compose.dev.yml     # ✅ Dev environment (uses env_file)
│   ├── docker-compose.test.yml    # ✅ Test environment (uses env_file)
│   ├── docker-compose.ci.yml      # ✅ CI environment (uses env_file)
│   └── docker-compose.prod.yml    # ✅ Production template
├── env/
|   ├── .env.example               # ✅ Non-prod template
│   ├── .env.dev                   # ✅ Dev config (gitignored)
│   ├── .env.test                  # ✅ Test config (gitignored)
│   ├── .env.ci                    # ✅ CI config (committed)
│   ├── .env.prod.example          # ✅ Production template
│   └── README.md                  # ✅ Environment docs
├── pyproject.toml                 # ✅ Source of truth for dependencies
├── uv.lock                        # ✅ Locked dependency versions
├── requirements.txt               # ⚠️  Keep for legacy/reference
└── requirements-dev.txt           # ⚠️  Keep for legacy/reference
```

**Benefits:**

- ✅ Non-root user in all environments
- ✅ Single source of truth for dependencies
- ✅ Environment variables in dedicated files
- ✅ Organized structure, clean root
- ✅ Reusable Dockerfile for all stages

---

## Phase 1: Backup & Preparation ✅ COMPLETED

**Status:** ✅ Done (files extracted and backed up)

```bash
✅ pyproject.toml extracted from running container
✅ uv.lock extracted from running container  
✅ pyproject.toml.backup created
✅ uv.lock.backup created
✅ email-validator dependency added
```

---

## Phase 2: Directory Reorganization

### Step 1: Create New Directory Structure

```bash
# Create compose directory
mkdir -p compose

# Create env directory
mkdir -p env

# Create docker directory contents
touch docker/.dockerignore
```

### Step 2: Move Compose Files

```bash
# Move compose files
mv docker-compose.dev.yml compose/
mv docker-compose.test.yml compose/
mv docker-compose.ci.yml compose/  # if exists
cp docker-compose.yml compose/docker-compose.prod.yml.example  # as template

# Delete unused base compose
rm docker-compose.yml
```

### Step 3: Reorganize Environment Files

```bash
# Move env files
mv .env.dev env/
mv .env.test env/
mv .env.ci env/  # if exists
cp .env.example env/.env.example
cp .env.example env/.env.prod.example

# Keep .env.example in root for compatibility
```

### Step 4: Update Symlinks/References

The Makefile needs to be updated to reference new paths.

---

## Phase 3: Dockerfile Refactoring

### New Dockerfile Structure

**Key Changes:**

1. ✅ Add non-root user to ALL stages
2. ✅ Use pyproject.toml + uv.lock (no requirements.txt)
3. ✅ Remove dynamic pyproject.toml creation
4. ✅ Proper file ownership with `--chown`
5. ✅ Support first-time setup AND consecutive builds

```dockerfile
# docker/Dockerfile
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
COPY --chown=appuser:appuser pyproject.toml* uv.lock* ./

# Install dependencies from lockfile
RUN uv sync --frozen

# Copy application code (as appuser)
COPY --chown=appuser:appuser . .

# Development command - run migrations then start with reload
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"]

# =============================================================================
# Builder Stage - Production dependency installation
# =============================================================================
FROM base AS builder

# Copy dependency files
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Install production dependencies only (no dev dependencies)
RUN if [ -f "uv.lock" ]; then \
        uv sync --frozen --no-dev; \
    else \
        echo "ERROR: No uv.lock found for production build!" && exit 1; \
    fi

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
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"]

# =============================================================================
# Callback Server Stage - OAuth callback handler
# =============================================================================
FROM python:3.13-slim AS callback

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Install required Python packages
RUN pip install --no-cache-dir requests urllib3

# Copy callback server
COPY --chown=appuser:appuser callback_server.py ./

# Switch to non-root user
USER appuser

# Run callback server
CMD ["python", "-u", "callback_server.py"]
```

### Key Features

**1. First-Time Setup Support:**

```dockerfile
RUN if [ ! -f "pyproject.toml" ]; then \
        uv init --app --name dashtam --python 3.13 --no-readme --no-pin-python; \
    else \
        uv sync --frozen; \
    fi
```

- If no pyproject.toml: Initialize fresh project
- If pyproject.toml exists: Use it and sync from lockfile

**2. Non-Root User Everywhere:**

```dockerfile
USER appuser
COPY --chown=appuser:appuser . .
```

- All stages run as appuser (UID 1000)
- Files owned by appuser:appuser
- No permission issues on host

**3. Lockfile-Based Builds:**

```dockerfile
uv sync --frozen  # Uses lockfile, no dependency resolution
```

- Fast builds (no resolution)
- Reproducible (exact versions)
- Cached layers

---

## Phase 4: Docker Compose Refactoring

### compose/docker-compose.dev.yml

```yaml
name: dashtam-dev

services:
  postgres:
    image: postgres:17.6-alpine3.22
    container_name: dashtam-dev-postgres
    env_file:
      - ../env/.env.dev
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-dashtam_user}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dashtam-dev-network

  redis:
    image: redis:8.2.1-alpine3.22
    container_name: dashtam-dev-redis
    env_file:
      - ../env/.env.dev
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_dev_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dashtam-dev-network

  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      target: development
    container_name: dashtam-dev-app
    env_file:
      - ../env/.env.dev
    ports:
      - "${APP_PORT:-8000}:8000"
    volumes:
      - ../src:/app/src:rw
      - ../tests:/app/tests:rw
      - ../alembic:/app/alembic:rw
      - ../alembic.ini:/app/alembic.ini:ro
      - ../certs:/app/certs:ro
      - ../pyproject.toml:/app/pyproject.toml:ro
      - ../uv.lock:/app/uv.lock:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - dashtam-dev-network
    restart: unless-stopped

  callback:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      target: callback
    container_name: dashtam-dev-callback
    env_file:
      - ../env/.env.dev
    ports:
      - "8182:8182"
    volumes:
      - ../certs:/app/certs:ro
    depends_on:
      - app
    networks:
      - dashtam-dev-network
    restart: unless-stopped

networks:
  dashtam-dev-network:
    driver: bridge

volumes:
  postgres_dev_data:
    driver: local
  redis_dev_data:
    driver: local
```

**Key Changes:**

- ✅ Uses `env_file: ../env/.env.dev` (no hardcoded vars)
- ✅ Mounts pyproject.toml and uv.lock as read-only
- ✅ alembic.ini as read-only (config shouldn't change)
- ✅ Relative paths from compose/ directory

---

## Phase 5: Makefile Updates

Update all Makefile commands to use new paths:

```makefile
# Development Environment
dev-up:
    @echo "🚀 Starting DEVELOPMENT environment..."
    @docker compose -f compose/docker-compose.dev.yml --env-file env/.env.dev up -d
    @echo "✅ Development services started!"

dev-down:
    @echo "🛑 Stopping DEVELOPMENT environment..."
    @docker compose -f compose/docker-compose.dev.yml down

dev-build:
    @echo "🏗️  Building DEVELOPMENT images..."
    @docker compose -f compose/docker-compose.dev.yml --env-file env/.env.dev build

# ... similar for test, ci environments ...
```

---

## Phase 6: Environment File Organization

### env/README.md

```markdown


    # Environment Configuration

    This directory contains environment-specific configuration files.

    ## Files

    - `.env.dev` - Development environment (gitignored)
    - `.env.test` - Test environment (gitignored)
    - `.env.ci` - CI environment (committed, no secrets)
    - `.env.prod.example` - Production template

    ## Usage

    Copy the example file:
    ```bash
    cp env/.env.prod.example env/.env.prod
    ```

    Edit with your values (NEVER commit .env.prod).

    ## Environment Priority

    1. Environment variables (highest)
    2. env_file in docker-compose
    3. Default values in code

    ## Required Variables

    See `.env.prod.example` for all required variables.

```

---

## Phase 7: .dockerignore

Create `docker/.dockerignore`:

```bash
# Git
.git/
.gitignore
.gitattributes

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/

# Virtual environments
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Documentation
docs/
*.md
!README.md

# Tests (exclude in production builds)
tests/
.pytest_cache/
.coverage
htmlcov/

# Environment files (sensitive)
.env*
!.env.example

# Backups
*.backup
*.bak

# Logs
*.log

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose*.yml
Dockerfile
.dockerignore
```

---

## Testing Strategy

### Step 1: Test Dev Environment

```bash
# Build
make dev-build

# Start
make dev-up

# Verify non-root user
docker compose -f compose/docker-compose.dev.yml exec app whoami
# Should output: appuser (not root!)

# Verify file ownership
docker compose -f compose/docker-compose.dev.yml exec app ls -la /app
# Should show: appuser appuser

# Test file creation
docker compose -f compose/docker-compose.dev.yml exec app touch /app/test.txt
ls -la test.txt
# Should show: faiyazhaider (your user), not root!

# Run tests
make test
```

### Step 2: Test Test Environment

```bash
make test-build
make test-up
make test
```

### Step 3: Test CI Environment

```bash
make ci-build
make ci-test
```

---

## Rollback Plan

If anything goes wrong:

```bash
# Restore backups
cp pyproject.toml.backup pyproject.toml
cp uv.lock.backup uv.lock

# Restore old compose files (from git)
git checkout docker-compose.dev.yml docker-compose.test.yml

# Rebuild
make dev-rebuild
```

---

## Migration Checklist

### Pre-Migration

- [x] Extract pyproject.toml from container
- [x] Extract uv.lock from container
- [x] Create backups
- [x] Add missing dependencies (email-validator)
- [ ] Review all current environment variables
- [ ] Document any custom configurations

### Migration

- [ ] Create directory structure (compose/, env/, docker/)
- [ ] Move compose files to compose/
- [ ] Move env files to env/
- [ ] Update Dockerfile with non-root user
- [ ] Update all compose files (env_file, paths)
- [ ] Update Makefile (new paths)
- [ ] Create .dockerignore
- [ ] Create env/README.md

### Testing

- [ ] Test dev build (no cache)
- [ ] Verify non-root user in dev
- [ ] Test file permissions
- [ ] Run full test suite
- [ ] Test CI build
- [ ] Verify env vars loaded correctly

### Documentation

- [ ] Update main README.md
- [ ] Update infrastructure docs
- [ ] Update WARP.md if needed
- [ ] Add migration notes

### Cleanup

- [ ] Remove old docker-compose.yml
- [ ] Remove requirements.txt (or mark as legacy)
- [ ] Remove requirements-dev.txt (or mark as legacy)
- [ ] Clean up unused files

---

## Benefits Summary

### Security

- ✅ Non-root user in all environments
- ✅ Proper file permissions
- ✅ Locked dependencies (auditable)

### Development Experience

- ✅ No sudo needed for file edits
- ✅ Files owned by developer user
- ✅ IDE file watchers work correctly

### Build Performance

- ✅ Faster builds (lockfile, no resolution)
- ✅ Better layer caching
- ✅ Reproducible builds

### Maintainability

- ✅ Clean root directory
- ✅ Organized structure
- ✅ Single source of truth (pyproject.toml)
- ✅ Clear separation of concerns

---

**Ready for Implementation:** ✅ Yes  
**Next Step:** Create directory structure and start Phase 2
