# Docker & Build Infrastructure Refactoring

Complete implementation plan for refactoring Docker and build infrastructure to improve security, maintainability, and development workflow.

---

## Table of Contents

- [Overview](#overview)
  - [Key Features](#key-features)
- [Purpose](#purpose)
- [Components](#components)
  - [Component 1: Multi-Stage Dockerfile](#component-1-multi-stage-dockerfile)
  - [Component 2: Docker Compose Configuration](#component-2-docker-compose-configuration)
  - [Component 3: Environment Configuration](#component-3-environment-configuration)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Configuration Files](#configuration-files)
  - [Ports and Services](#ports-and-services)
- [Setup Instructions](#setup-instructions)
  - [Prerequisites](#prerequisites)
  - [Installation Steps](#installation-steps)
    - [Step 1: Backup Current Configuration](#step-1-backup-current-configuration)
    - [Step 2: Create Directory Structure](#step-2-create-directory-structure)
    - [Step 3: Move Configuration Files](#step-3-move-configuration-files)
    - [Step 4: Update Dockerfile](#step-4-update-dockerfile)
    - [Step 5: Update Makefile](#step-5-update-makefile)
- [Operation](#operation)
  - [Starting the System](#starting-the-system)
  - [Stopping the System](#stopping-the-system)
  - [Restarting](#restarting)
  - [Checking Status](#checking-status)
- [Monitoring](#monitoring)
  - [Health Checks](#health-checks)
  - [Metrics to Monitor](#metrics-to-monitor)
  - [Logs](#logs)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Permission Denied Errors](#issue-1-permission-denied-errors)
  - [Issue 2: Environment Variables Not Loading](#issue-2-environment-variables-not-loading)
  - [Issue 3: Build Failures](#issue-3-build-failures)
- [Maintenance](#maintenance)
  - [Regular Tasks](#regular-tasks)
  - [Backup Procedures](#backup-procedures)
  - [Update Procedures](#update-procedures)
- [Security](#security)
  - [Security Considerations](#security-considerations)
  - [Access Control](#access-control)
  - [Network Security](#network-security)
- [Performance Optimization](#performance-optimization)
  - [Performance Tuning](#performance-tuning)
  - [Resource Limits](#resource-limits)
- [References](#references)

---

## Overview

This infrastructure refactoring addresses critical security, maintainability, and development workflow issues identified in the Docker and build system audit. The refactoring implements best practices for container security, dependency management, and development environment consistency.

### Key Features

- **Non-root container execution**: All services run as appuser (UID 1000)
- **UV-based dependency management**: Modern Python package management with lockfiles
- **Organized directory structure**: Clean separation of compose files, environment configs, and Docker assets
- **Environment isolation**: Dedicated configurations for dev, test, CI, and production
- **Security hardening**: Proper file permissions and access controls

## Purpose

The Docker infrastructure refactoring solves several critical problems:

- **Security vulnerabilities**: Eliminates root user execution in containers
- **File permission issues**: Prevents IDE and development workflow problems
- **Build inconsistency**: Establishes reproducible builds with lockfiles
- **Environment management**: Organizes configuration files for better maintainability
- **Development experience**: Improves developer workflow and onboarding

## Components

### Component 1: Multi-Stage Dockerfile

**Purpose:** Unified container definition supporting development, testing, and production environments

**Technology:** Docker multi-stage builds with UV package manager

**Dependencies:**

- ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim base image
- Non-root appuser (UID 1000)
- pyproject.toml and uv.lock files

**Key Features:**

- Base stage: Common setup for all environments
- Development stage: Hot reload with full tooling
- Builder stage: Production dependency installation
- Production stage: Minimal runtime
- Callback stage: OAuth callback handler

### Component 2: Docker Compose Configuration

**Purpose:** Environment-specific service orchestration

**Technology:** Docker Compose with environment file integration

**Dependencies:**

- PostgreSQL 17.6 (database)
- Redis 8.2.1 (cache)
- Environment configuration files

**Structure:**

- `compose/docker-compose.dev.yml` - Development environment
- `compose/docker-compose.test.yml` - Test environment  
- `compose/docker-compose.ci.yml` - CI/CD environment
- `compose/docker-compose.prod.yml` - Production template

### Component 3: Environment Configuration

**Purpose:** Centralized environment variable management

**Technology:** Environment files with Docker Compose integration

**Structure:**

- `env/.env.dev` - Development settings (gitignored)
- `env/.env.test` - Test settings (gitignored)
- `env/.env.ci` - CI settings (committed, no secrets)
- `env/.env.prod.example` - Production template

## Configuration

### Environment Variables

```bash
# Database Configuration
POSTGRES_USER=dashtam_user
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=dashtam_db
POSTGRES_PORT=5432

# Redis Configuration
REDIS_PORT=6379

# Application Configuration
APP_PORT=8000
DEBUG=true
```

### Configuration Files

**File:** `docker/Dockerfile`

```dockerfile
# Multi-stage Dockerfile with non-root user
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base
# ... (see full implementation below)
```

**Purpose:** Unified container definition for all environments

**File:** `compose/docker-compose.dev.yml`

```yaml
name: dashtam-dev
services:
  app:
    env_file:
      - ../env/.env.dev
    # ... (see full configuration below)
```

**Purpose:** Development environment orchestration

### Ports and Services

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| FastAPI App | 8000 | HTTPS | Main application |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache and sessions |
| OAuth Callback | 8182 | HTTPS | OAuth redirect handler |

## Setup Instructions

### Prerequisites

- [ ] Docker Desktop installed and running
- [ ] Make utility available
- [ ] Git repository with current codebase
- [ ] Existing pyproject.toml and uv.lock files

### Installation Steps

#### Step 1: Backup Current Configuration

```bash
# Create backups of critical files
cp pyproject.toml pyproject.toml.backup
cp uv.lock uv.lock.backup
```

**Verification:**

```bash
# Verify backups exist
ls -la *.backup
```

#### Step 2: Create Directory Structure

```bash
# Create new directory structure
mkdir -p compose env docker

# Create .dockerignore file
touch docker/.dockerignore
```

**Verification:**

```bash
# Check directory structure
tree -a compose env docker
```

#### Step 3: Move Configuration Files

```bash
# Move compose files to new location
mv docker-compose.dev.yml compose/
mv docker-compose.test.yml compose/
mv docker-compose.ci.yml compose/  # if exists

# Move environment files
mv .env.dev env/ 2>/dev/null || true
mv .env.test env/ 2>/dev/null || true
mv .env.ci env/ 2>/dev/null || true

# Create production template
cp .env.example env/.env.prod.example
```

#### Step 4: Update Dockerfile

Create the new multi-stage Dockerfile with non-root user:

```dockerfile
# docker/Dockerfile - Multi-stage build with non-root user
# syntax=docker/dockerfile:1

# Base Stage - Common setup
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl make && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000)
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Set working directory and ownership
WORKDIR /app
RUN chown appuser:appuser /app
USER appuser

# Environment variables for UV and Python
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:$PATH"

# Development Stage - Hot reload, full tooling
FROM base AS development
COPY --chown=appuser:appuser pyproject.toml* uv.lock* ./
RUN uv sync --frozen
COPY --chown=appuser:appuser . .
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"]

# Production Stage - Minimal runtime
FROM python:3.13-slim AS production
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && rm -rf /var/lib/apt/lists/*
RUN groupadd -r appuser -g 1000 && useradd -r -u 1000 -g appuser -m -s /bin/bash appuser
WORKDIR /app
COPY --from=base --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser . .
USER appuser
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f https://localhost:8000/health --insecure || exit 1
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
```

#### Step 5: Update Makefile

Update Makefile commands to use new directory structure:

```makefile
# Development Environment
dev-up:
    @docker compose -f compose/docker-compose.dev.yml --env-file env/.env.dev up -d

dev-down:
    @docker compose -f compose/docker-compose.dev.yml down

# Test Environment  
test-up:
    @docker compose -f compose/docker-compose.test.yml --env-file env/.env.test up -d
```

## Operation

### Starting the System

```bash
# Start development environment
make dev-up

# Or directly with docker compose
docker compose -f compose/docker-compose.dev.yml up -d
```

### Stopping the System

```bash
# Stop development environment
make dev-down

# Or directly with docker compose
docker compose -f compose/docker-compose.dev.yml down
```

### Restarting

```bash
# Restart development environment
make dev-restart
```

### Checking Status

```bash
# Check service status
make dev-status

# Or directly check
docker compose -f compose/docker-compose.dev.yml ps
```

**Expected Output:**

```text
NAME                   IMAGE                COMMAND                  SERVICE             CREATED              STATUS                        PORTS
dashtam-dev-app        dashtam-dev-app      "sh -c 'uv run alemb…"   app                 About a minute ago   Up About a minute (healthy)   0.0.0.0:8000->8000/tcp
dashtam-dev-postgres   postgres:17.6        "docker-entrypoint.s…"   postgres            About a minute ago   Up About a minute (healthy)   0.0.0.0:5432->5432/tcp
```

## Monitoring

### Health Checks

```bash
# Check application health
curl -k https://localhost:8000/health

# Check container health
docker compose -f compose/docker-compose.dev.yml exec app whoami
```

### Metrics to Monitor

- **Container user**: Should always be "appuser" (never root)
- **File ownership**: All files should be owned by appuser:appuser
- **Build performance**: Leverages layer caching for faster builds
- **Memory usage**: Production containers use minimal resources

### Logs

**Location:** Docker container logs

**Viewing Logs:**

```bash
# View application logs
docker compose -f compose/docker-compose.dev.yml logs app

# Follow logs in real-time
docker compose -f compose/docker-compose.dev.yml logs -f app
```

## Troubleshooting

### Issue 1: Permission Denied Errors

**Symptoms:**

- Cannot edit files created in container
- IDE file watchers not working
- "Permission denied" when running commands

**Diagnosis:**

```bash
# Check container user
docker compose -f compose/docker-compose.dev.yml exec app whoami
# Should output: appuser

# Check file ownership
docker compose -f compose/docker-compose.dev.yml exec app ls -la /app
# Should show: appuser appuser
```

**Solution:**

```bash
# Rebuild with no cache to ensure non-root user
make dev-rebuild
```

### Issue 2: Environment Variables Not Loading

**Symptoms:**

- Database connection errors
- Missing configuration values
- Default values being used instead of custom ones

**Diagnosis:**

```bash
# Check if env file exists
ls -la env/.env.dev

# Check environment variables in container
docker compose -f compose/docker-compose.dev.yml exec app env | grep POSTGRES
```

**Solution:**

```bash
# Create missing env file
cp env/.env.example env/.env.dev
# Edit with correct values
vim env/.env.dev
```

### Issue 3: Build Failures

**Symptoms:**

- "No such file or directory" errors
- UV sync failures
- Missing dependencies

**Diagnosis:**

```bash
# Check if required files exist
ls -la pyproject.toml uv.lock

# Check for syntax errors
uv check
```

**Solution:**

```bash
# Regenerate lockfile if needed
uv lock

# Clean build with no cache
docker compose -f compose/docker-compose.dev.yml build --no-cache
```

## Maintenance

### Regular Tasks

- **Daily:** Check container health and logs
- **Weekly:** Update base images and dependencies  
- **Monthly:** Review and optimize Docker layer caching

### Backup Procedures

```bash
# Backup critical files before changes
cp pyproject.toml pyproject.toml.backup
cp uv.lock uv.lock.backup
cp -r compose compose.backup
```

### Update Procedures

```bash
# Update UV version in Dockerfile
# Update base image versions
# Rebuild all environments
make dev-rebuild
make test-rebuild
```

## Security

### Security Considerations

- **Non-root execution**: All containers run as appuser (UID 1000) to prevent privilege escalation
- **Minimal attack surface**: Production images contain only required dependencies
- **Secret management**: Environment files are gitignored and never committed
- **Network isolation**: Services communicate through dedicated Docker networks

### Access Control

All containers enforce non-root user execution. File permissions are managed through proper ownership (appuser:appuser) and Docker volume mounts.

### Network Security

- Services isolated in dedicated Docker networks
- HTTPS enforced with SSL certificates
- Internal service communication through service names

## Performance Optimization

### Performance Tuning

- **Layer caching**: Optimized Dockerfile layer ordering for maximum cache hits
- **Multi-stage builds**: Separate build and runtime stages to minimize image size
- **Lockfile builds**: UV uses frozen lockfile for fast, reproducible builds

### Resource Limits

```yaml
# Example resource limits for production
services:
  app:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
        reservations:
          cpus: "1.0"
          memory: 2G
```

## References

- [Docker Multi-Stage Builds](https://docs.docker.com/develop/dev-best-practices/)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Docker Compose Environment Files](https://docs.docker.com/compose/environment-variables/)
- [Container Security Best Practices](https://docs.docker.com/develop/security-best-practices/)

---

## Document Information

**Category:** Infrastructure
**Created:** 2025-10-05
**Last Updated:** 2025-10-15
**Component Type:** Docker, Container orchestration, Build system

**Maintainer:** Dashtam Development Team
