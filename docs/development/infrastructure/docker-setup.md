# Docker Multi-Environment Setup

Comprehensive guide to Dashtam's Docker-based multi-environment infrastructure with isolated development, testing, and CI/CD environments.

---

## Table of Contents

- [Overview](#overview)
  - [Key Features](#key-features)
  - [Architecture Diagram](#architecture-diagram)
- [Purpose](#purpose)
  - [Problem 1: Container Conflicts](#problem-1-container-conflicts)
  - [Problem 2: Data Contamination](#problem-2-data-contamination)
  - [Problem 3: Manual Workflow](#problem-3-manual-workflow)
  - [Problem 4: CI/CD Integration](#problem-4-cicd-integration)
  - [Problem 5: SSL Testing Gap](#problem-5-ssl-testing-gap)
- [Components](#components)
  - [Development Environment](#development-environment)
  - [Test Environment](#test-environment)
  - [CI/CD Environment](#cicd-environment)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Docker Compose Files](#docker-compose-files)
  - [Ports and Services](#ports-and-services)
- [Setup Instructions](#setup-instructions)
  - [Prerequisites](#prerequisites)
  - [First-Time Setup](#first-time-setup)
    - [Step 1: Clone Repository](#step-1-clone-repository)
    - [Step 2: Generate SSL Certificates](#step-2-generate-ssl-certificates)
    - [Step 3: Create Environment Files](#step-3-create-environment-files)
    - [Step 4: Start Development Environment](#step-4-start-development-environment)
  - [SSL Certificates](#ssl-certificates)
- [Operation](#operation)
  - [Development Workflow](#development-workflow)
  - [Testing Workflow](#testing-workflow)
  - [CI/CD Workflow](#cicd-workflow)
- [Monitoring](#monitoring)
  - [Health Checks](#health-checks)
  - [Service Status](#service-status)
  - [Logs](#logs)
- [Troubleshooting](#troubleshooting)
  - [Container Name Conflicts](#container-name-conflicts)
  - [Port Already in Use](#port-already-in-use)
  - [Database Connection Errors](#database-connection-errors)
  - [SSL Certificate Issues](#ssl-certificate-issues)
- [Maintenance](#maintenance)
  - [Updating Images](#updating-images)
  - [Cleaning Up Resources](#cleaning-up-resources)
  - [Backup and Restore](#backup-and-restore)
- [Security](#security)
  - [Network Isolation](#network-isolation)
  - [SSL/TLS Configuration](#ssltls-configuration)
  - [Secrets Management](#secrets-management)
- [Performance Optimization](#performance-optimization)
  - [CI/CD Optimizations](#cicd-optimizations)
  - [Development Speed](#development-speed)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

Dashtam uses a **multi-environment Docker architecture** that provides complete isolation between development, testing, and CI/CD workflows. Each environment runs independently with its own containers, networks, and storage.

### Key Features

- **Parallel Execution**: Run development and testing simultaneously without conflicts
- **Complete Isolation**: Separate networks, containers, and data for each environment
- **Ephemeral Testing**: Test and CI environments use tmpfs for speed and clean state
- **Health Monitoring**: Built-in health checks for all services
- **Fast Feedback**: CI optimized for maximum speed with PostgreSQL tuning
- **SSL Everywhere**: HTTPS support in all environments for production parity

### Architecture Diagram

```mermaid
graph TB
    subgraph Dev [Development Environment]
        DevApp[dashtam-dev-app<br/>Port 8000]
        DevDB[dashtam-dev-postgres<br/>Port 5432]
        DevRedis[dashtam-dev-redis<br/>Port 6379]
        DevCallback[dashtam-dev-callback<br/>Port 8182]
        DevApp --> DevDB
        DevApp --> DevRedis
    end
    
    subgraph Test [Test Environment]
        TestApp[dashtam-test-app<br/>Port 8001]
        TestDB[dashtam-test-postgres<br/>Port 5433]
        TestRedis[dashtam-test-redis<br/>Port 6380]
        TestCallback[dashtam-test-callback<br/>Port 8183]
        TestApp --> TestDB
        TestApp --> TestRedis
    end
    
    subgraph CI [CI/CD Environment]
        CIApp[dashtam-ci-app<br/>Internal only]
        CIDB[dashtam-ci-postgres<br/>Internal only]
        CIRedis[dashtam-ci-redis<br/>Internal only]
        CICallback[dashtam-ci-callback<br/>Internal only]
        CIApp --> CIDB
        CIApp --> CIRedis
    end
    
    DevNet[dashtam-dev-network]
    TestNet[dashtam-test-network]
    CINet[dashtam-ci-network]
    
    Dev -.-> DevNet
    Test -.-> TestNet
    CI -.-> CINet
    
    style DevApp fill:#e8f5e9
    style TestApp fill:#fff3e0
    style CIApp fill:#e3f2fd
```

## Purpose

The multi-environment architecture solves critical problems:

### Problem 1: Container Conflicts

- **Before**: Single docker-compose.yml caused name/port conflicts
- **After**: Unique names and ports per environment enable parallel execution

### Problem 2: Data Contamination

- **Before**: Shared PostgreSQL volume risked dev data contaminating tests
- **After**: Separate storage (persistent dev, ephemeral test/CI) ensures isolation

### Problem 3: Manual Workflow

- **Before**: `make test-setup` required stopping dev, starting test manually
- **After**: `make test` runs tests while dev keeps running

### Problem 4: CI/CD Integration

- **Before**: No dedicated CI configuration, unreliable test execution
- **After**: Optimized CI compose file with speed tuning and automation

### Problem 5: SSL Testing Gap

- **Before**: Tests ran without SSL, OAuth flows untested
- **After**: SSL certificates available in all environments

## Components

### Development Environment

**File**: `compose/docker-compose.dev.yml`

**Services**:

- **dashtam-dev-postgres** - PostgreSQL 17.6 with persistent volume
- **dashtam-dev-redis** - Redis 8.2.1 with AOF persistence
- **dashtam-dev-app** - FastAPI application with hot reload
- **dashtam-dev-callback** - OAuth callback server (HTTPS)

**Purpose**: Active development with live code reload and persistent data

**Storage**: Named volumes (`postgres_dev_data`, `redis_dev_data`)

**Network**: `dashtam-dev-network` (bridge)

### Test Environment

**File**: `compose/docker-compose.test.yml`

**Services**:

- **dashtam-test-postgres** - PostgreSQL with tmpfs (ephemeral)
- **dashtam-test-redis** - Redis with tmpfs, no persistence
- **dashtam-test-app** - Application container for test execution
- **dashtam-test-callback** - OAuth callback for OAuth tests

**Purpose**: Local testing with clean state and parallel execution

**Storage**: tmpfs (ephemeral, fast, always clean)

**Network**: `dashtam-test-network` (bridge, isolated)

### CI/CD Environment

**File**: `compose/docker-compose.ci.yml`

**Services**:

- **dashtam-ci-postgres** - Speed-optimized PostgreSQL (synchronous_commit=off)
- **dashtam-ci-redis** - Minimal Redis (no persistence, no saves)
- **dashtam-ci-app** - Application for automated test execution
- **dashtam-ci-callback** - OAuth callback for CI OAuth tests

**Purpose**: Automated testing in GitHub Actions

**Storage**: tmpfs with aggressive tuning for maximum speed

**Network**: `dashtam-ci-network` (internal only, no port mappings)

## Configuration

### Environment Variables

Each environment has its own `.env` file in `env/` directory:

**Development** (`env/.env.dev`):

```bash
# Application
DEBUG=true
APP_PORT=8000

# Database
POSTGRES_DB=dashtam
POSTGRES_USER=dashtam_user
POSTGRES_PASSWORD=dev_password
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://dashtam_user:dev_password@postgres:5432/dashtam

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0

# OAuth
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182

# Security
SECRET_KEY=dev-secret-key-change-in-production
ENCRYPTION_KEY=dev-encryption-key-change-in-production
```

**Testing** (`env/.env.test`):

```bash
# Application
DEBUG=true
TESTING=true
APP_PORT=8000  # Internal port (mapped to 8001 externally)

# Database
POSTGRES_DB=dashtam_test
POSTGRES_USER=dashtam_test_user
POSTGRES_PASSWORD=test_password
POSTGRES_PORT=5432  # Internal port (mapped to 5433 externally)
DATABASE_URL=postgresql+asyncpg://dashtam_test_user:test_password@postgres:5432/dashtam_test

# Redis
REDIS_HOST=redis
REDIS_PORT=6379  # Internal port (mapped to 6380 externally)
REDIS_DB=1
REDIS_URL=redis://redis:6379/1

# OAuth
SCHWAB_REDIRECT_URI=https://127.0.0.1:8183
```

**CI/CD** (`env/.env.ci`):

```bash
# Application
DEBUG=false
TESTING=true

# Database (speed optimized)
POSTGRES_DB=dashtam_test
POSTGRES_USER=dashtam_test_user
POSTGRES_PASSWORD=ci_password
DATABASE_URL=postgresql+asyncpg://dashtam_test_user:ci_password@postgres:5432/dashtam_test

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1
REDIS_URL=redis://redis:6379/1

# No port mappings in CI (internal only)
```

### Docker Compose Files

All compose files located in `compose/` directory:

| File | Purpose | Usage |
|------|---------|-------|
| `docker-compose.dev.yml` | Development | `make dev-up` |
| `docker-compose.test.yml` | Local testing | `make test-up` |
| `docker-compose.ci.yml` | CI/CD automation | GitHub Actions |

### Ports and Services

| Environment | Service | Internal Port | External Port | Protocol |
|-------------|---------|---------------|---------------|----------|
| **Development** | FastAPI App | 8000 | 8000 | HTTPS |
| | PostgreSQL | 5432 | 5432 | TCP |
| | Redis | 6379 | 6379 | TCP |
| | OAuth Callback | 8182 | 8182 | HTTPS |
| **Test** | FastAPI App | 8000 | 8001 | HTTPS |
| | PostgreSQL | 5432 | 5433 | TCP |
| | Redis | 6379 | 6380 | TCP |
| | OAuth Callback | 8182 | 8183 | HTTPS |
| **CI/CD** | FastAPI App | 8000 | (none) | Internal |
| | PostgreSQL | 5432 | (none) | Internal |
| | Redis | 6379 | (none) | Internal |
| | OAuth Callback | 8182 | (none) | Internal |

**Key Design**:

- Development uses standard ports
- Test uses offset ports (+1, +1001, +1001, +1) to avoid conflicts
- CI uses no external ports (internal communication only)

## Setup Instructions

### Prerequisites

- [ ] Docker Desktop installed (v20.10+)
- [ ] Docker Compose v2 (included in Docker Desktop)
- [ ] Make utility installed
- [ ] OpenSSL (for SSL certificate generation)

### First-Time Setup

#### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/dashtam.git
cd dashtam
```

#### Step 2: Generate SSL Certificates

```bash
make certs
```

**Verification:**

```bash
ls -la certs/
# Expected: cert.pem, key.pem
```

#### Step 3: Create Environment Files

```bash
# Copy example files
cp env/.env.dev.example env/.env.dev
cp env/.env.test.example env/.env.test
cp env/.env.ci.example env/.env.ci

# Generate secure keys
make keys
```

#### Step 4: Start Development Environment

```bash
make dev-up
```

**Verification:**

```bash
curl -k https://localhost:8000/health
# Expected: {"status":"ok"}
```

### SSL Certificates

**Generate Self-Signed Certificates:**

```bash
make certs
```

This creates `certs/cert.pem` and `certs/key.pem` for HTTPS in all environments.

**Browser Warning**: Self-signed certificates trigger browser warnings - this is expected in development.

**Production**: Replace with proper certificates from Let's Encrypt or your certificate authority.

## Operation

### Development Workflow

**Start Development:**

```bash
make dev-up
```

**View Logs:**

```bash
make dev-logs              # All services
make dev-logs-app          # FastAPI only
make dev-logs-postgres     # PostgreSQL only
```

**Access Services:**

- FastAPI: https://localhost:8000
- API Docs: https://localhost:8000/docs
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

**Shell Access:**

```bash
make dev-shell             # Application shell
make dev-db-shell          # PostgreSQL shell
make dev-redis-cli         # Redis CLI
```

**Stop Development:**

```bash
make dev-down
```

**Rebuild Images:**

```bash
make dev-rebuild           # Full rebuild from scratch
```

### Testing Workflow

**Start Test Environment:**

```bash
make test-up
```

**Run Tests:**

```bash
make test                  # All tests with coverage
make test-unit             # Unit tests only
make test-integration      # Integration tests only
make test-smoke            # Smoke tests (end-to-end)
```

**Run Specific Tests:**

```bash
make test-verify           # Quick verification (core tests)
docker compose -f compose/docker-compose.test.yml exec app \
    pytest tests/unit/test_encryption.py -v
```

**Test with Development Running:**

```bash
# Terminal 1: Dev environment
make dev-up
make dev-logs

# Terminal 2: Tests (parallel)
make test
```

**Clean Up:**

```bash
make test-down
```

### CI/CD Workflow

**Used by GitHub Actions** - see `.github/workflows/test.yml`:

```yaml
- name: Start test environment
  run: docker compose -f compose/docker-compose.ci.yml up -d --build

- name: Run tests
  run: |
    docker compose -f compose/docker-compose.ci.yml exec -T app \
      uv run pytest tests/ -v --cov=src
```

**Local CI Testing:**

```bash
make ci-test
```

## Monitoring

### Health Checks

All services have built-in health checks:

**Check Development:**

```bash
docker compose -f compose/docker-compose.dev.yml ps
```

**Expected Output:**

```text
NAME                    STATUS        HEALTH
dashtam-dev-app         Up            healthy
dashtam-dev-postgres    Up            healthy (5s)
dashtam-dev-redis       Up            healthy (3s)
dashtam-dev-callback    Up
```

**Check Specific Service:**

```bash
docker inspect --format='{{.State.Health.Status}}' dashtam-dev-postgres
# Output: healthy
```

### Service Status

**All Environments:**

```bash
make status-all
```

**Development Only:**

```bash
make dev-status
```

**Test Only:**

```bash
make test-status
```

### Logs

**Development Logs:**

```bash
make dev-logs              # Follow all logs
make dev-logs-app          # FastAPI only
make dev-logs-postgres     # Database only
make dev-logs-redis        # Cache only
make dev-logs-callback     # OAuth callback only
```

**Test Logs:**

```bash
docker compose -f compose/docker-compose.test.yml logs -f
```

**Key Log Indicators:**

- ✅ **Success**: "Migrations completed successfully", "Uvicorn running on..."
- ✅ **Database Ready**: "database system is ready to accept connections"
- ✅ **Redis Ready**: "Ready to accept connections"
- ❌ **Error**: Check for "ERROR", "FATAL", "refused" in logs

## Troubleshooting

### Container Name Conflicts

**Symptoms:**

- Error: "Container name 'dashtam-app' already in use"
- Cannot start environment

**Diagnosis:**

```bash
docker ps -a | grep dashtam
```

**Solution:**

```bash
# Stop all environments
make dev-down
make test-down

# Or force remove
docker rm -f $(docker ps -aq --filter name=dashtam)
```

### Port Already in Use

**Symptoms:**

- Error: "bind: address already in use"
- Port 8000, 5432, or 6379 conflict

**Diagnosis:**

```bash
# Check what's using the port
lsof -i :8000
netstat -an | grep 8000
```

**Solution:**

```bash
# Option 1: Stop conflicting service
kill <PID>

# Option 2: Use test environment (different ports)
make test-up  # Uses 8001, 5433, 6380

# Option 3: Change port in env/.env.dev
APP_PORT=8080  # Instead of 8000
```

### Database Connection Errors

**Symptoms:**

- "connection refused"
- "could not connect to server"

**Diagnosis:**

```bash
# Check if PostgreSQL is healthy
docker inspect dashtam-dev-postgres --format='{{.State.Health.Status}}'

# Check logs
make dev-logs-postgres
```

**Solution:**

```bash
# Wait for health check
docker compose -f compose/docker-compose.dev.yml \
    wait postgres

# Or restart database
docker compose -f compose/docker-compose.dev.yml restart postgres
```

### SSL Certificate Issues

**Symptoms:**

- "SSL: CERTIFICATE_VERIFY_FAILED"
- Browser shows "Your connection is not private"

**Diagnosis:**

```bash
# Check if certificates exist
ls -la certs/

# Verify certificate validity
openssl x509 -in certs/cert.pem -text -noout
```

**Solution:**

```bash
# Regenerate certificates
make certs

# In dev, use -k flag with curl
curl -k https://localhost:8000/health

# In Python/pytest, SSL warnings are expected
# (tests use fixtures that handle SSL)
```

## Maintenance

### Updating Images

**Update Base Images:**

```bash
# Pull latest PostgreSQL/Redis
docker pull postgres:17.6-alpine3.22
docker pull redis:8.2.1-alpine3.22

# Rebuild application
make dev-rebuild
make test-rebuild
```

**Update Python Dependencies:**

```bash
# Inside dev container
make dev-shell
uv add package-name

# Rebuild to apply
make dev-rebuild
```

### Cleaning Up Resources

**Remove Unused Volumes:**

```bash
docker volume prune
```

**Remove All Dashtam Resources:**

```bash
make clean
```

**Full System Cleanup:**

```bash
docker system prune -a --volumes
# WARNING: Removes ALL unused Docker resources
```

### Backup and Restore

**Backup Development Database:**

```bash
docker compose -f compose/docker-compose.dev.yml exec postgres \
    pg_dump -U dashtam_user dashtam > backup.sql
```

**Restore Development Database:**

```bash
docker compose -f compose/docker-compose.dev.yml exec -T postgres \
    psql -U dashtam_user -d dashtam < backup.sql
```

**Backup Named Volumes:**

```bash
docker run --rm -v postgres_dev_data:/data -v $(pwd):/backup \
    alpine tar czf /backup/postgres_dev_data.tar.gz -C /data .
```

## Security

### Network Isolation

Each environment has its own isolated Docker bridge network:

- **dashtam-dev-network** - Development isolation
- **dashtam-test-network** - Test isolation
- **dashtam-ci-network** - CI isolation

**No cross-environment communication** is possible.

**Verification:**

```bash
docker network ls | grep dashtam
docker network inspect dashtam-dev-network
```

### SSL/TLS Configuration

All environments use HTTPS:

- **Self-signed certificates** in development/test
- **Proper certificates** required in production

**Certificate Location**: `certs/cert.pem`, `certs/key.pem`

**Mounted Read-Only**: All containers mount certs as `:ro` (read-only)

### Secrets Management

**Development**: Secrets in `env/.env.dev` (gitignored)

**Testing**: Mock secrets in `env/.env.test`

**CI/CD**: GitHub Secrets → `env/.env.ci` (generated in CI)

**Production**: Use environment variables or secrets manager (AWS Secrets Manager, HashiCorp Vault)

**Never commit**:

- `.env` files (actual secrets)
- `certs/` directory (SSL keys)

**Safe to commit**:

- `.env.example` files (templates)

## Performance Optimization

### CI/CD Optimizations

The CI compose file includes aggressive PostgreSQL tuning:

```yaml
command: >
  postgres
  -c synchronous_commit=off       # Faster commits
  -c fsync=off                    # Skip disk sync
  -c full_page_writes=off         # Reduce I/O
  -c shared_buffers=256MB         # More memory
  -c effective_cache_size=512MB   # Cache tuning
```

**Why it's safe**:

- CI runs are atomic (isolated sessions)
- Data is ephemeral (tmpfs, no persistence)
- Each job starts with fresh database
- No data sharing between jobs

**Speed Impact**: ~30-50% faster test execution

### Development Speed

**Fast Code Reload**: Source code mounted as volumes with hot reload

**Persistent Data**: Development database survives restarts (no re-seeding)

**Health Checks**: Services wait for dependencies (no manual timing)

## References

- [Environment Flows](environment-flows.md) - Detailed environment switching guide
- [Database Migrations](database-migrations.md) - Alembic integration with Docker
- [CI/CD Setup](ci-cd.md) - GitHub Actions configuration
- [Docker Refactoring Implementation](../guides/docker-refactoring-implementation.md) - Migration history
- [Docker Documentation](https://docs.docker.com/compose/)
- [UV Package Management](../guides/uv-package-management.md) - Python dependency management

---

## Document Information

**Template:** [infrastructure-template.md](../../templates/infrastructure-template.md)
**Created:** 2025-10-17
**Last Updated:** 2025-10-17
