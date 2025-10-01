# Infrastructure Migration Implementation Plan

## Overview

This document outlines the step-by-step plan to migrate Dashtam from the current overlay-based Docker Compose setup to a production-ready, parallel-environment architecture following industry best practices.

## Migration Goals

1. ✅ Enable parallel dev and test environments
2. ✅ Eliminate container name conflicts
3. ✅ Remove `sleep infinity` workarounds
4. ✅ Add SSL testing capabilities
5. ✅ Prepare for CI/CD integration
6. ✅ Improve developer experience
7. ✅ Ensure complete environment isolation

## Timeline

- **Phase 1** (Critical): ~2-3 days - Separate environments and verify parallel execution
- **Phase 2** (Important): ~2-3 days - SSL testing, CI/CD setup, health checks
- **Phase 3** (Validation): ~1-2 days - End-to-end testing, cleanup, documentation

**Total Estimated Time**: 5-8 days

---

## Phase 1: Environment Separation (Critical)

### Step 1.1: Backup Current Configuration ✅
**Risk**: Low | **Priority**: Critical

**Actions**:
```bash
# Create backup directory
mkdir -p backups/pre-migration-$(date +%Y%m%d)

# Backup all config files
cp docker-compose.yml backups/pre-migration-$(date +%Y%m%d)/
cp docker-compose.test.yml backups/pre-migration-$(date +%Y%m%d)/
cp .env backups/pre-migration-$(date +%Y%m%d)/
cp .env.test backups/pre-migration-$(date +%Y%m%d)/
cp Makefile backups/pre-migration-$(date +%Y%m%d)/

# Verify backups
ls -la backups/pre-migration-$(date +%Y%m%d)/
```

**Verification**:
- [ ] All 5 files backed up successfully
- [ ] Backup directory contains correct files
- [ ] File sizes match originals

---

### Step 1.2: Create docker-compose.dev.yml
**Risk**: Low | **Priority**: Critical

**Actions**:
1. Copy `docker-compose.yml` to `docker-compose.dev.yml`
2. Update all container names with `-dev` suffix
3. Update network name to `dashtam-dev-network`
4. Update volume names with `-dev` suffix
5. Keep all ports unchanged (8000, 5432, 6379, 8182)

**Key Changes**:
```yaml
services:
  app:
    container_name: dashtam-dev-app    # was: dashtam-app
    networks:
      - dev-network                     # was: dashtam-network
  
  postgres:
    container_name: dashtam-dev-postgres
    volumes:
      - dev_postgres_data:/var/lib/postgresql/data

networks:
  dev-network:
    name: dashtam-dev-network           # was: dashtam-network

volumes:
  dev_postgres_data:                    # was: postgres_data
  dev_redis_data:                       # was: redis_data
```

**Verification**:
- [ ] File created successfully
- [ ] All container names have `-dev` suffix
- [ ] Network name updated
- [ ] Ports remain unchanged
- [ ] File is valid YAML (no syntax errors)

---

### Step 1.3: Rename .env to .env.dev
**Risk**: Low | **Priority**: Critical

**Actions**:
```bash
# Rename environment file
mv .env .env.dev

# Verify
ls -la | grep env
```

**Verification**:
- [ ] .env.dev exists
- [ ] Old .env file no longer exists
- [ ] File contents unchanged

---

### Step 1.4: Refactor docker-compose.test.yml
**Risk**: Medium | **Priority**: Critical

**Actions**:
1. Rewrite as completely standalone (remove overlay dependencies)
2. Add `-test` suffix to all container names
3. Change ports: 8001 (app), 5433 (postgres), 6380 (redis), 8183 (callback)
4. Use separate network: `dashtam-test-network`
5. Use tmpfs for PostgreSQL (ephemeral, fast)
6. Remove `sleep infinity` - use proper `docker-compose run`
7. Add depends_on with health checks

**Key Structure**:
```yaml
services:
  postgres:
    container_name: dashtam-test-postgres
    ports:
      - "5433:5432"  # Different port!
    tmpfs:
      - /var/lib/postgresql/data  # Ephemeral storage
    networks:
      - test-network
  
  redis:
    container_name: dashtam-test-redis
    ports:
      - "6380:6379"  # Different port!
    networks:
      - test-network
  
  app:
    container_name: dashtam-test-app
    ports:
      - "8001:8000"  # Different port!
    networks:
      - test-network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    # NO command: sleep infinity!

networks:
  test-network:
    name: dashtam-test-network
```

**Verification**:
- [ ] File is standalone (no references to base compose file)
- [ ] All ports are different from dev
- [ ] Network is separate
- [ ] No `sleep infinity` command
- [ ] Health checks configured
- [ ] File is valid YAML

---

### Step 1.5: Update Makefile
**Risk**: Medium | **Priority**: Critical

**New Targets**:
```makefile
# Development Environment
dev-up:
	docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d

dev-down:
	docker-compose -f docker-compose.dev.yml --env-file .env.dev down

dev-logs:
	docker-compose -f docker-compose.dev.yml --env-file .env.dev logs -f

dev-shell:
	docker-compose -f docker-compose.dev.yml --env-file .env.dev exec app bash

dev-restart:
	docker-compose -f docker-compose.dev.yml --env-file .env.dev restart

# Test Environment
test-up:
	docker-compose -f docker-compose.test.yml --env-file .env.test up -d

test-down:
	docker-compose -f docker-compose.test.yml --env-file .env.test down -v

test-unit:
	docker-compose -f docker-compose.test.yml --env-file .env.test run --rm app uv run pytest tests/unit/ -v

test-integration:
	docker-compose -f docker-compose.test.yml --env-file .env.test run --rm app uv run pytest tests/integration/ -v

test-all:
	docker-compose -f docker-compose.test.yml --env-file .env.test run --rm app uv run pytest tests/ -v --cov=src

# Backward compatibility (temporary)
up: dev-up
down: dev-down
logs: dev-logs
```

**Verification**:
- [ ] All new targets added
- [ ] Backward compatibility aliases work
- [ ] --env-file flags present on all commands
- [ ] Makefile syntax is valid

---

### Step 1.6: Verify Dev Environment
**Risk**: Low | **Priority**: Critical

**Test Sequence**:
```bash
# 1. Clean slate
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v

# 2. Start dev environment
make dev-up

# 3. Wait for services
sleep 10

# 4. Check containers
docker ps | grep dev

# 5. Test app accessibility
curl -k https://localhost:8000

# 6. Check logs
make dev-logs | head -50

# 7. Test database
docker exec dashtam-dev-postgres psql -U dashtam_user -d dashtam -c "SELECT 1"

# 8. Stop cleanly
make dev-down
```

**Verification Checklist**:
- [ ] All 4 dev containers start successfully
- [ ] App responds on port 8000
- [ ] Database is accessible
- [ ] Redis is healthy
- [ ] Callback server is running
- [ ] No error messages in logs
- [ ] Containers stop cleanly

---

### Step 1.7: Verify Test Environment
**Risk**: Medium | **Priority**: Critical

**Test Sequence**:
```bash
# 1. Clean slate
make test-down

# 2. Start test environment
make test-up

# 3. Check containers
docker ps | grep test

# 4. Verify different ports
curl -k https://localhost:8001 || echo "Expected - app not running yet"

# 5. Run tests
make test-unit

# 6. Check test database
docker exec dashtam-test-postgres psql -U dashtam_test_user -d dashtam_test -c "SELECT 1"

# 7. Clean up
make test-down
```

**Verification Checklist**:
- [ ] All test containers start on different ports
- [ ] No port conflicts with dev
- [ ] Tests run successfully
- [ ] Test database is isolated
- [ ] Containers clean up properly (tmpfs)
- [ ] No leftover volumes

---

### Step 1.8: Verify Parallel Execution
**Risk**: High | **Priority**: Critical

**Test Sequence**:
```bash
# 1. Start dev environment
make dev-up
sleep 5

# 2. Verify dev is running
curl -k https://localhost:8000
echo "Dev app running on 8000"

# 3. Start test environment (while dev is running!)
make test-up
sleep 5

# 4. Check both are running
docker ps | grep dashtam

# 5. Verify ports
curl -k https://localhost:8000 && echo "Dev accessible"
# Test app won't respond (no command running) - this is expected

# 6. Run tests while dev runs
make test-unit

# 7. Verify dev still works
curl -k https://localhost:8000 && echo "Dev still running"

# 8. Clean up
make test-down
make dev-down
```

**Verification Checklist**:
- [ ] Dev and test run simultaneously without conflicts
- [ ] Dev app accessible on 8000
- [ ] Test containers on different ports (8001, 5433, 6380)
- [ ] Networks are isolated
- [ ] Tests run successfully while dev runs
- [ ] No cross-contamination of data
- [ ] Both environments stop cleanly

---

## Phase 2: Enhanced Features (Important)

### Step 2.1: Add SSL Testing Support
**Risk**: Low | **Priority**: High

**Actions**:
1. Mount SSL certs to test containers
2. Add SSL_ENABLED env variable
3. Create integration test profile with SSL
4. Update test config to handle SSL conditionally

**Changes to docker-compose.test.yml**:
```yaml
services:
  app:
    volumes:
      - ./certs:/app/certs:ro  # Add SSL certs
    environment:
      - SSL_ENABLED=${SSL_ENABLED:-false}
  
  # Optional: separate service for SSL testing
  app-ssl:
    extends: app
    container_name: dashtam-test-app-ssl
    environment:
      - SSL_ENABLED=true
    command: >
      sh -c "uv run python src/core/init_test_db.py &&
             uv run uvicorn src.main:app
             --host 0.0.0.0 --port 8000
             --ssl-keyfile=certs/key.pem
             --ssl-certfile=certs/cert.pem"
```

**Verification**:
- [ ] SSL certs mounted successfully
- [ ] Unit tests run without SSL (fast)
- [ ] Integration tests can enable SSL
- [ ] OAuth tests work with HTTPS

---

### Step 2.2: Create docker-compose.ci.yml
**Risk**: Low | **Priority**: High

**Structure**:
```yaml
# Optimized for CI/CD
services:
  postgres:
    tmpfs:
      - /var/lib/postgresql/data
    # No port mapping (internal only)
    environment:
      POSTGRES_HOST_AUTH_METHOD: trust
  
  redis:
    tmpfs:
      - /data
  
  app:
    # No port mapping
    depends_on:
      postgres:
        condition: service_healthy
    command: >
      sh -c "uv run python src/core/init_test_db.py &&
             uv run pytest tests/ -v --cov=src --cov-report=xml"
```

**Verification**:
- [ ] No external port mappings
- [ ] Optimized for speed (tmpfs)
- [ ] Health checks present
- [ ] Tests run automatically
- [ ] Exit code reflects test results

---

### Step 2.3: Create .env.ci
**Risk**: Low | **Priority**: Medium

**Contents**:
```bash
# CI/CD Environment
ENVIRONMENT=ci
TESTING=true
DEBUG=false

# Database (fast settings)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/dashtam_test
POSTGRES_DB=dashtam_test
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Mock credentials
SCHWAB_API_KEY=ci_mock_key
SCHWAB_API_SECRET=ci_mock_secret

# Disable external calls
DISABLE_EXTERNAL_CALLS=true
MOCK_PROVIDERS=true

# Speed optimizations
SSL_ENABLED=false
DB_ECHO=false
```

**Verification**:
- [ ] All required variables present
- [ ] No real credentials
- [ ] Optimized for CI/CD speed

---

### Step 2.4: Implement Health Checks
**Risk**: Low | **Priority**: Medium

**Add to all compose files**:
```yaml
services:
  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
  
  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
```

**Verification**:
- [ ] Health checks defined for all services
- [ ] Intervals are reasonable
- [ ] Containers marked healthy when ready
- [ ] Dependencies wait for health

---

### Step 2.5: Create GitHub Actions Workflow (Optional)
**Risk**: Low | **Priority**: Low (but recommended)

**Create**: `.github/workflows/test.yml`

**Basic workflow**:
```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run tests
        run: |
          cp .env.ci .env.test
          docker-compose -f docker-compose.ci.yml build
          docker-compose -f docker-compose.ci.yml up --abort-on-container-exit
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        if: success()
        with:
          files: ./coverage.xml
```

**Verification**:
- [ ] Workflow file is valid YAML
- [ ] Tests run on push/PR
- [ ] Coverage uploaded if configured

---

### Step 2.6: Update Documentation
**Risk**: Low | **Priority**: High

**Files to Update**:
1. **README.md**: New commands, workflow
2. **WARP.md**: Container names, commands
3. **ARCHITECTURE_GUIDE.md**: New architecture
4. Create **MIGRATION_GUIDE.md** for team

**Verification**:
- [ ] All documentation updated
- [ ] Commands are accurate
- [ ] Examples work
- [ ] Migration guide complete

---

## Phase 3: Validation & Cleanup

### Step 3.1: End-to-End Testing
**Risk**: High | **Priority**: Critical

**Complete Test Sequence**:
```bash
# 1. Clean environment
docker system prune -f
make dev-down
make test-down

# 2. Start dev
make dev-up
# Verify dev works

# 3. Make code change
# Verify hot reload

# 4. Run tests (while dev running)
make test-unit
make test-integration

# 5. Verify both coexist
docker ps
netstat -an | grep LISTEN | grep -E "(8000|8001|5432|5433)"

# 6. Clean up
make test-down
make dev-down
```

**Verification**:
- [ ] Dev environment works end-to-end
- [ ] Test environment works end-to-end
- [ ] Both run in parallel
- [ ] No conflicts or errors
- [ ] Hot reload works in dev
- [ ] Tests pass

---

### Step 3.2: Cleanup
**Risk**: Low | **Priority**: Medium

**Actions**:
```bash
# Move old files
mv docker-compose.yml docker-compose.yml.old
mv docker-compose.test.yml.old docker-compose.test.yml.old.backup

# Update .gitignore
echo ".env.dev" >> .gitignore
echo ".env.test" >> .gitignore
echo ".env.ci" >> .gitignore
echo "docker-compose.*.old" >> .gitignore
```

**Verification**:
- [ ] Old files backed up
- [ ] .gitignore updated
- [ ] No sensitive data committed

---

### Step 3.3: Rollback Documentation
**Risk**: Low | **Priority**: Medium

**Create**: `ROLLBACK_PROCEDURE.md`

**Contents**:
- List of all changed files
- Commands to restore backups
- Known issues and solutions
- Contact information

**Verification**:
- [ ] Rollback procedure documented
- [ ] Tested rollback works
- [ ] Team aware of procedure

---

### Step 3.4: Final Validation
**Risk**: Critical | **Priority**: Critical

**Final Checklist**:
- [ ] All Phase 1 steps completed and verified
- [ ] All Phase 2 steps completed and verified
- [ ] All Phase 3 steps completed and verified
- [ ] Dev environment works perfectly
- [ ] Test environment works perfectly
- [ ] Parallel execution confirmed
- [ ] CI/CD ready
- [ ] Documentation complete
- [ ] No regressions
- [ ] Team sign-off obtained

---

## Success Criteria

✅ **Dev and test run simultaneously without conflicts**
✅ **No more `sleep infinity` workarounds**
✅ **SSL testing capability added**
✅ **CI/CD integration ready**
✅ **Better developer experience**
✅ **Complete environment isolation**
✅ **All tests pass**
✅ **Documentation complete**

---

## Risk Mitigation

- **Backups created** before any changes
- **Incremental approach** - can stop at any phase
- **Verification at each step** - catch issues early
- **Rollback procedure** documented
- **Team can continue dev** - non-blocking migration

---

## Next Steps After Completion

1. Add staging environment (docker-compose.staging.yml)
2. Implement monitoring/observability
3. Add performance optimizations
4. Consider Kubernetes migration for production
5. Implement blue-green deployments

---

## Questions or Issues?

If any step fails or is unclear:
1. Check the verification checklist
2. Review error logs
3. Consult ROLLBACK_PROCEDURE.md if needed
4. Don't proceed to next step until current step verified
