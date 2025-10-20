# Docker & Build Infrastructure Refactoring

Complete implementation plan for refactoring Docker and build infrastructure to improve security, maintainability, and development workflow.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [Key Features](#key-features)
  - [Components Overview](#components-overview)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Backup Current Configuration](#step-1-backup-current-configuration)
  - [Step 2: Create Directory Structure](#step-2-create-directory-structure)
  - [Step 3: Move Configuration Files](#step-3-move-configuration-files)
  - [Step 4: Update Dockerfile](#step-4-update-dockerfile)
  - [Step 5: Update Makefile](#step-5-update-makefile)
  - [Step 6: Configure Environment Variables](#step-6-configure-environment-variables)
- [Examples](#examples)
  - [Example 1: Starting the Development Environment](#example-1-starting-the-development-environment)
  - [Example 2: Rebuilding After Changes](#example-2-rebuilding-after-changes)
- [Verification](#verification)
  - [Check 1: Verify Container User](#check-1-verify-container-user)
  - [Check 2: Verify Health Status](#check-2-verify-health-status)
  - [Check 3: Monitor Logs](#check-3-monitor-logs)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Permission Denied Errors](#issue-1-permission-denied-errors)
  - [Issue 2: Environment Variables Not Loading](#issue-2-environment-variables-not-loading)
  - [Issue 3: Build Failures](#issue-3-build-failures)
- [Best Practices](#best-practices)
  - [Security Best Practices](#security-best-practices)
  - [Performance Best Practices](#performance-best-practices)
  - [Maintenance Best Practices](#maintenance-best-practices)
- [Next Steps](#next-steps)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

This infrastructure refactoring addresses critical security, maintainability, and development workflow issues identified in the Docker and build system audit. The refactoring implements best practices for container security, dependency management, and development environment consistency.

### What You'll Learn

- How to implement non-root container execution for enhanced security
- How to organize Docker files with modern UV package management
- How to set up environment-specific configurations (dev, test, CI, production)
- How to troubleshoot common Docker infrastructure issues
- Best practices for secure and performant Docker deployments

### Key Features

- **Non-root container execution**: All services run as appuser (UID 1000)
- **UV-based dependency management**: Modern Python package management with lockfiles
- **Organized directory structure**: Clean separation of compose files, environment configs, and Docker assets
- **Environment isolation**: Dedicated configurations for dev, test, CI, and production
- **Security hardening**: Proper file permissions and access controls

### Components Overview

The Docker infrastructure refactoring solves several critical problems:

- **Security vulnerabilities**: Eliminates root user execution in containers
- **File permission issues**: Prevents IDE and development workflow problems
- **Build inconsistency**: Establishes reproducible builds with lockfiles
- **Environment management**: Organizes configuration files for better maintainability
- **Development experience**: Improves developer workflow and onboarding

**Architecture Components:**

1. **Multi-Stage Dockerfile** - Unified container definition supporting development, testing, and production
2. **Docker Compose Configuration** - Environment-specific service orchestration
3. **Environment Configuration** - Centralized environment variable management

## Prerequisites

Before starting, ensure you have:

- [ ] Docker Desktop installed and running
- [ ] Make utility available
- [ ] Git repository with current codebase
- [ ] Existing pyproject.toml and uv.lock files

**Required Tools:**

- Docker Desktop - Latest version
- Make - For project commands
- UV 0.8.22+ - Python package manager

**Required Knowledge:**

- Familiarity with Docker and Docker Compose
- Basic understanding of multi-stage builds
- Understanding of environment variables

## Step-by-Step Instructions

### Step 1: Backup Current Configuration

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

### Step 6: Configure Environment Variables

Create environment files for each environment with appropriate values:

```bash
# Create development environment file
cp env/.env.example env/.env.dev

# Edit with development values
vim env/.env.dev
```

**Required Variables:**

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

**Service Ports:**

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| FastAPI App | 8000 | HTTPS | Main application |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache and sessions |
| OAuth Callback | 8182 | HTTPS | OAuth redirect handler |

**What This Does:** Sets up environment-specific configuration for each deployment environment.

## Examples

### Example 1: Starting the Development Environment

Complete workflow for starting and managing the development environment:

```bash
# 1. Start all services
make dev-up

# 2. Check service status
make dev-status

# 3. View logs
make dev-logs

# 4. Stop services when done
make dev-down
```

**Result:** Development environment running with all services healthy.

**Expected Output:**

```text
NAME                   IMAGE                COMMAND                  SERVICE             CREATED              STATUS                        PORTS
dashtam-dev-app        dashtam-dev-app      "sh -c 'uv run alemb…"   app                 About a minute ago   Up About a minute (healthy)   0.0.0.0:8000->8000/tcp
dashtam-dev-postgres   postgres:17.6        "docker-entrypoint.s…"   postgres            About a minute ago   Up About a minute (healthy)   0.0.0.0:5432->5432/tcp
```

### Example 2: Rebuilding After Changes

When you make changes to Dockerfile or dependencies:

```bash
# 1. Stop current environment
make dev-down

# 2. Rebuild with no cache
make dev-rebuild

# 3. Start with fresh build
make dev-up

# 4. Verify build success
make dev-status
```

**Result:** Fresh Docker images with latest changes applied.

## Verification

### Check 1: Verify Container User

```bash
# Check container user
docker compose -f compose/docker-compose.dev.yml exec app whoami
```

**Expected Result:** Should output `appuser` (never root)

### Check 2: Verify Health Status

```bash
# Check application health
curl -k https://localhost:8000/health

# Check all service health
docker compose -f compose/docker-compose.dev.yml ps
```

**Expected Result:** All services show "healthy" status

**Metrics to Verify:**

- Container user is "appuser" (non-root)
- All files owned by appuser:appuser
- Services respond to health checks
- No permission errors in logs

### Check 3: Monitor Logs

```bash
# View application logs
docker compose -f compose/docker-compose.dev.yml logs app

# Follow logs in real-time
make dev-logs
```

**Expected Result:** No errors, successful startup messages, no permission denied errors

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

## Best Practices

### Security Best Practices

✅ **Non-root Execution**

- Always run containers as non-root user (appuser, UID 1000)
- Prevents privilege escalation attacks
- Maintains file permission consistency

✅ **Secret Management**

- Never commit environment files to version control
- Use `.gitignore` for all `.env.*` files (except `.example`)
- Rotate secrets regularly in production

✅ **Minimal Attack Surface**

- Production images contain only required dependencies
- Use multi-stage builds to exclude development tools
- Regularly update base images for security patches

✅ **Network Isolation**

- Services communicate through dedicated Docker networks
- HTTPS enforced with SSL certificates
- Internal service communication uses service names (not IPs)

### Performance Best Practices

✅ **Layer Caching Optimization**

- Copy dependency files (`pyproject.toml`, `uv.lock`) before source code
- Maximize cache hits during rebuilds
- Order Dockerfile instructions from least to most frequently changing

✅ **Multi-Stage Builds**

- Separate build and runtime stages
- Minimize production image size
- Exclude development dependencies from production

✅ **Lockfile Builds**

- Use `uv sync --frozen` for deterministic builds
- Ensures reproducible environments across machines
- Fast, cached dependency installation

✅ **Resource Limits**

```yaml
# Production resource limits
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

### Maintenance Best Practices

✅ **Regular Maintenance Schedule**

- **Daily**: Check container health and logs
- **Weekly**: Update base images and dependencies
- **Monthly**: Review and optimize Docker layer caching
- **Quarterly**: Audit security configurations

✅ **Backup Procedures**

```bash
# Always backup before major changes
cp pyproject.toml pyproject.toml.backup
cp uv.lock uv.lock.backup
cp -r compose compose.backup
```

✅ **Update Workflow**

```bash
# 1. Update UV version in Dockerfile
# 2. Update base image versions
# 3. Test in development first
make dev-rebuild
make test

# 4. Then update other environments
make test-rebuild
```

✅ **File Ownership**

- All files should be owned by `appuser:appuser`
- Fix permissions if needed: `chown -R appuser:appuser /app`
- Verify with: `ls -la` inside container

## Next Steps

After completing the Docker infrastructure refactoring, consider these next steps:

- [ ] **Set up CI/CD integration** - Configure GitHub Actions to use the new Docker structure
- [ ] **Implement production deployment** - Use `docker-compose.prod.yml` as template for production
- [ ] **Configure monitoring** - Add Prometheus/Grafana for production monitoring
- [ ] **Set up log aggregation** - Implement centralized logging (ELK stack or CloudWatch)
- [ ] **Document team workflows** - Create runbooks for common operations
- [ ] **Test disaster recovery** - Verify backup and restore procedures work correctly
- [ ] **Optimize for production** - Fine-tune resource limits based on actual usage patterns
- [ ] **Security audit** - Perform comprehensive security review of Docker configuration
- [ ] **Add health monitoring** - Implement comprehensive health checks for all services

## References

- [Docker Multi-Stage Builds](https://docs.docker.com/develop/dev-best-practices/)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Docker Compose Environment Files](https://docs.docker.com/compose/environment-variables/)
- [Container Security Best Practices](https://docs.docker.com/develop/security-best-practices/)

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-05
**Last Updated:** 2025-10-15
