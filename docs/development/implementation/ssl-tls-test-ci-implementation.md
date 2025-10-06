# SSL/TLS in Test and CI Environments - Implementation Plan

**Date**: 2025-10-06  
**Status**: ✅ **COMPLETE**  
**Priority**: P0 (High Impact)  
**Completed**: 2025-10-06

---

## Table of Contents
- [Executive Summary](#executive-summary)
- [Current State](#current-state)
- [Implementation Strategy](#implementation-strategy)
- [Step-by-Step Implementation](#step-by-step-implementation)
- [Testing & Verification](#testing--verification)
- [Rollback Plan](#rollback-plan)

---

## Executive Summary

**Objective**: Enable SSL/TLS (HTTPS) in test and CI environments to match development environment configuration, achieving **production parity** across all environments.

**Status**: ✅ **COMPLETE - All environments now use HTTPS with self-signed certificates**

**Scope**:
- ✅ Test environment (`docker-compose.test.yml`) - **ENABLED** ✅
- ✅ CI environment (`docker-compose.ci.yml`) - **ENABLED** ✅
- ✅ Update environment configurations (`.env.test`, `.env.ci`) - **DONE** ✅
- ✅ Update pytest fixtures for HTTPS testing - **DONE** ✅
- ✅ Verify all 305 tests still pass - **PASSING** ✅
- ✅ Fix PostgreSQL health check errors - **FIXED** ✅
- ✅ Commit self-signed certificates to git - **DONE** ✅

**Impact Achieved**:
- 🔒 Production parity: All environments use HTTPS ✅
- 🐛 Catch SSL-specific bugs earlier ✅
- ✅ Test realistic HTTPS scenarios ✅
- 🚀 OAuth providers work correctly (some require HTTPS) ✅

**Actual Effort**: 2 hours  
**Risk**: Low (self-signed certs, existing infrastructure)  
**Result**: ✅ Success - All tests passing in all environments

---

## Current State

### Development Environment (dev) ✅
```yaml
# compose/docker-compose.dev.yml
services:
  app:
    ports:
      - "8000:8000"  # HTTPS
    volumes:
      - ../certs:/app/certs:ro  # ✅ SSL certs mounted
```

```bash
# env/.env.dev
SSL_CERT_FILE=certs/cert.pem  # ✅ Configured
SSL_KEY_FILE=certs/key.pem    # ✅ Configured
API_BASE_URL=https://localhost:8000  # ✅ HTTPS
```

**Status**: ✅ **HTTPS Enabled and Working**

---

### Test Environment (test) ⚠️
```yaml
# compose/docker-compose.test.yml
services:
  app:
    ports:
      - "8001:8000"  # Port exposed
    volumes:
      - ../certs:/app/certs:ro  # ✅ SSL certs mounted
```

```bash
# env/.env.test
SSL_CERT_FILE=certs/cert.pem  # ✅ Cert files configured
SSL_KEY_FILE=certs/key.pem    # ✅ Cert files configured
CORS_ORIGINS=http://localhost:3000  # ❌ HTTP only
SCHWAB_REDIRECT_URI=http://localhost:8183/callback  # ❌ HTTP only
```

**Status**: ⚠️ **SSL Available but Using HTTP**

**Issues**:
- Certs are mounted and configured
- But URLs are HTTP (not HTTPS)
- CORS origins list HTTP only
- OAuth callbacks using HTTP

---

### CI Environment (ci) ❌
```yaml
# compose/docker-compose.ci.yml
services:
  app:
    # No ports exposed (internal only)
    # ❌ No SSL cert volumes
```

```bash
# env/.env.ci
API_BASE_URL=http://app:8000  # ❌ HTTP only
CALLBACK_BASE_URL=http://callback:8182  # ❌ HTTP only
# ❌ No SSL cert/key configuration
```

**Status**: ❌ **No SSL Support**

**Issues**:
- No SSL certificate volumes mounted
- No SSL configuration in env file
- All URLs use HTTP
- Production parity gap

---

## Implementation Strategy

### Approach: Enable SSL with Self-Signed Certificates

**Why Self-Signed Certs?**
- ✅ Already used in dev environment
- ✅ Already generated (`make certs`)
- ✅ No external dependencies
- ✅ Fast and simple
- ✅ Perfect for test/CI environments

**Production Parity**:
- Dev: HTTPS with self-signed certs ✅
- Test: HTTPS with self-signed certs ← **Enable this**
- CI: HTTPS with self-signed certs ← **Enable this**
- Staging: HTTPS with proper certs (future)
- Production: HTTPS with proper certs (future)

---

### Changes Required

#### 1. Test Environment
- ✅ Update `.env.test` - Change HTTP URLs to HTTPS
- ✅ Update CORS origins to HTTPS
- ✅ No docker-compose changes needed (certs already mounted)

#### 2. CI Environment
- ✅ Update `.env.ci` - Add SSL configuration, change URLs to HTTPS
- ✅ Update `docker-compose.ci.yml` - Mount SSL certs
- ✅ Update GitHub Actions workflow - Ensure certs available

#### 3. Test Configuration
- ✅ Update pytest fixtures to use HTTPS
- ✅ Configure test client to accept self-signed certs
- ✅ Verify all 305 tests still pass

---

## Step-by-Step Implementation

### Phase 1: Test Environment (30 minutes)

#### Step 1.1: Update `.env.test` for HTTPS

```bash
# env/.env.test
# Change HTTP to HTTPS
CORS_ORIGINS=https://localhost:3000,https://localhost:8001,https://test

# Already correct (keep as-is)
SSL_CERT_FILE=certs/cert.pem
SSL_KEY_FILE=certs/key.pem
CALLBACK_SSL_CERT_FILE=certs/callback_cert.pem
CALLBACK_SSL_KEY_FILE=certs/callback_key.pem

# Update OAuth redirect URI to HTTPS
SCHWAB_REDIRECT_URI=https://localhost:8183/callback
```

**File Changes**:
```diff
--- a/env/.env.test
+++ b/env/.env.test
@@ -32,11 +32,11 @@
 REFRESH_TOKEN_EXPIRE_DAYS=30
 
 # CORS Configuration (relaxed for testing)
-CORS_ORIGINS=http://localhost:3000,http://localhost:8001,http://test
+CORS_ORIGINS=https://localhost:3000,https://localhost:8001,https://test
 
 # Mock Provider Configuration for Testing
 SCHWAB_API_KEY=test_schwab_client_id
 SCHWAB_API_SECRET=test_schwab_client_secret
 SCHWAB_API_BASE_URL=http://localhost:8999/mock/schwab
-SCHWAB_REDIRECT_URI=http://localhost:8183/callback
+SCHWAB_REDIRECT_URI=https://localhost:8183/callback
```

#### Step 1.2: Update pytest fixtures for HTTPS

**File**: `tests/conftest.py`

```python
# Add or update base_url fixture to use HTTPS
@pytest.fixture(scope="session")
def base_url():
    """Base URL for API tests (HTTPS in all environments)."""
    import os
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "testing":
        # Test environment - internal Docker hostname
        return "https://app:8000"
    else:
        # Development environment
        return "https://localhost:8000"

# Add fixture to disable SSL warnings for self-signed certs
@pytest.fixture(scope="session", autouse=True)
def disable_ssl_warnings():
    """Disable SSL warnings for self-signed certs in test environments."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Update http_client fixture to handle self-signed certs
@pytest.fixture
def http_client():
    """HTTP client configured for test environment SSL."""
    import httpx
    
    # Accept self-signed certs in test/dev environments
    return httpx.AsyncClient(verify=False)
```

#### Step 1.3: Verify docker-compose.test.yml (No Changes Needed)

```yaml
# compose/docker-compose.test.yml - Already correct!
services:
  app:
    volumes:
      - ../certs:/app/certs:ro  # ✅ Certs already mounted
```

---

### Phase 2: CI Environment (30 minutes)

#### Step 2.1: Update `.env.ci` for HTTPS

```bash
# env/.env.ci
# Add SSL Configuration
SSL_CERT_FILE=certs/cert.pem
SSL_KEY_FILE=certs/key.pem
CALLBACK_SSL_CERT_FILE=certs/callback_cert.pem
CALLBACK_SSL_KEY_FILE=certs/callback_key.pem

# Change URLs from HTTP to HTTPS
API_BASE_URL=https://app:8000
CALLBACK_BASE_URL=https://callback:8182

# CORS Configuration (for CI internal testing)
CORS_ORIGINS=https://app:8000,https://localhost:8000
```

**File Changes**:
```diff
--- a/env/.env.ci
+++ b/env/.env.ci
@@ -10,8 +10,13 @@
 LOG_LEVEL=WARNING
 
 # Application URLs (internal Docker network communication)
-API_BASE_URL=http://app:8000
-CALLBACK_BASE_URL=http://callback:8182
+API_BASE_URL=https://app:8000
+CALLBACK_BASE_URL=https://callback:8182
+
+# SSL/TLS Configuration (self-signed certs for CI)
+SSL_CERT_FILE=certs/cert.pem
+SSL_KEY_FILE=certs/key.pem
+CALLBACK_SSL_CERT_FILE=certs/callback_cert.pem
+CALLBACK_SSL_KEY_FILE=certs/callback_key.pem
 
 # PostgreSQL Configuration
 POSTGRES_DB=dashtam_test
```

#### Step 2.2: Update `docker-compose.ci.yml` to mount certs

```yaml
# compose/docker-compose.ci.yml
services:
  app:
    env_file:
      - ../env/.env.ci
    volumes:
      - ../src:/app/src:ro
      - ../tests:/app/tests:ro
      - ../alembic:/app/alembic:ro
      - ../alembic.ini:/app/alembic.ini:ro
      - ../certs:/app/certs:ro  # ← ADD THIS LINE
      - ../pyproject.toml:/app/pyproject.toml:ro
      - ../uv.lock:/app/uv.lock:ro
```

**File Changes**:
```diff
--- a/compose/docker-compose.ci.yml
+++ b/compose/docker-compose.ci.yml
@@ -82,6 +82,7 @@ services:
       - ../tests:/app/tests:ro
       - ../alembic:/app/alembic:ro
       - ../alembic.ini:/app/alembic.ini:ro
+      - ../certs:/app/certs:ro
       - ../pyproject.toml:/app/pyproject.toml:ro
       - ../uv.lock:/app/uv.lock:ro
     depends_on:
```

#### Step 2.3: Update `docker-compose.ci.yml` callback server

```yaml
# compose/docker-compose.ci.yml
services:
  callback:
    env_file:
      - ../env/.env.ci
    volumes:
      - ../certs:/app/certs:ro  # ← ADD THIS LINE
```

**File Changes**:
```diff
--- a/compose/docker-compose.ci.yml
+++ b/compose/docker-compose.ci.yml
@@ -121,6 +121,8 @@ services:
     env_file:
       - ../env/.env.ci
     # No port mapping - internal communication only in CI
+    volumes:
+      - ../certs:/app/certs:ro
     depends_on:
       - app
     networks:
```

#### Step 2.4: Verify GitHub Actions has certs

**Check**: `.github/workflows/test.yml`

The workflow already checks out the code, which includes the `certs/` directory. No changes needed unless certs are in `.gitignore`.

**Verify certs are committed**:
```bash
git ls-files certs/
# Should show:
# certs/cert.pem
# certs/key.pem
# certs/callback_cert.pem
# certs/callback_key.pem
```

**If certs are not committed** (they should be for dev/test):
```bash
# Check .gitignore
cat .gitignore | grep certs

# If certs/ is ignored, we need to commit them or generate in CI
# For dev/test, self-signed certs should be committed
git add certs/*.pem
git commit -m "chore(certs): commit self-signed dev/test SSL certificates"
```

---

### Phase 3: Testing & Verification (30 minutes)

#### Step 3.1: Test Environment Verification

```bash
# 1. Start test environment
make test-up

# 2. Check app is using HTTPS
docker compose -f compose/docker-compose.test.yml logs app | grep -i "ssl\|https\|uvicorn"
# Should see: "Uvicorn running on https://0.0.0.0:8000"

# 3. Test HTTPS endpoint manually
curl -k https://localhost:8001/health
# Should return: {"status":"healthy","database":"connected","version":"0.1.0"}

# 4. Run full test suite
make test
# All 305 tests should pass

# 5. Check for SSL warnings
# Should see minimal/no warnings about SSL verification
```

#### Step 3.2: CI Environment Verification

```bash
# 1. Test CI environment locally
make ci-build
make ci-test

# Should see:
# - App starting with HTTPS
# - All 305 tests passing
# - No SSL-related errors

# 2. Push changes and verify in GitHub Actions
git add env/.env.test env/.env.ci compose/docker-compose.ci.yml tests/conftest.py
git commit -m "feat(infra): enable SSL/TLS in test and CI environments

- Update .env.test to use HTTPS URLs
- Update .env.ci with SSL configuration and HTTPS URLs
- Mount SSL certs in CI docker-compose
- Update pytest fixtures to handle HTTPS with self-signed certs
- Disable SSL warnings for self-signed certs in tests

Achieves production parity: all environments (dev, test, CI) now use HTTPS."

git push origin development

# 3. Monitor GitHub Actions
gh pr checks --watch
```

---

## Complete Implementation Script

**Copy-paste ready commands** (30-45 minutes total):

```bash
#!/bin/bash
# Enable SSL/TLS in Test and CI Environments
set -e

cd /Users/faiyazhaider/Dashtam

echo "🔐 Step 1: Update Test Environment Configuration"

# Update .env.test for HTTPS
cat > env/.env.test << 'EOF'
# Test Environment Configuration
# This file contains test-specific environment variables

# Application Configuration
APP_NAME=Dashtam
APP_VERSION=0.1.0
ENVIRONMENT=testing
DEBUG=true
API_V1_PREFIX=/api/v1

# Server Configuration (different ports for testing)
HOST=0.0.0.0
PORT=8001
RELOAD=false

# Test Database Configuration
# Use Docker internal hostname 'postgres' not 'localhost'
DATABASE_URL=postgresql+asyncpg://dashtam_test_user:test_password@postgres:5432/dashtam_test
DB_ECHO=false

# PostgreSQL Configuration
POSTGRES_DB=dashtam_test
POSTGRES_USER=dashtam_test_user
POSTGRES_PASSWORD=test_password
POSTGRES_PORT=5432

# Security Configuration (test keys)
SECRET_KEY=test-secret-key-for-automated-testing-only-never-use-in-production
ENCRYPTION_KEY=test-encryption-key-32-chars-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# CORS Configuration (HTTPS for production parity)
CORS_ORIGINS=https://localhost:3000,https://localhost:8001,https://test

# SSL/TLS Configuration (using existing certs for test environment)
SSL_CERT_FILE=certs/cert.pem
SSL_KEY_FILE=certs/key.pem

# Callback Server Configuration
CALLBACK_SERVER_HOST=0.0.0.0
CALLBACK_SERVER_PORT=8183
CALLBACK_SSL_CERT_FILE=certs/callback_cert.pem
CALLBACK_SSL_KEY_FILE=certs/callback_key.pem

# Mock Provider Configuration for Testing
SCHWAB_API_KEY=test_schwab_client_id
SCHWAB_API_SECRET=test_schwab_client_secret
SCHWAB_API_BASE_URL=http://localhost:8999/mock/schwab
SCHWAB_REDIRECT_URI=https://localhost:8183/callback

# Plaid Configuration (mocked)
PLAID_CLIENT_ID=test_plaid_client_id
PLAID_SECRET=test_plaid_secret
PLAID_ENVIRONMENT=sandbox

# Redis Configuration
# Use Docker internal hostname 'redis' not 'localhost'
REDIS_URL=redis://redis:6379/1
REDIS_PORT=6379

# Test-specific flags
TESTING=true
DISABLE_EXTERNAL_CALLS=true
MOCK_PROVIDERS=true
FAST_ENCRYPTION=true
EOF

echo "✅ Updated env/.env.test"

echo ""
echo "🔐 Step 2: Update CI Environment Configuration"

# Update .env.ci for HTTPS
cat > env/.env.ci << 'EOF'
# CI/CD Environment Configuration
# This file contains CI-specific environment variables for automated testing

# Application Configuration
APP_NAME=Dashtam
APP_VERSION=0.1.0
ENVIRONMENT=testing
DEBUG=false
LOG_LEVEL=WARNING

# Application URLs (internal Docker network communication - HTTPS)
API_BASE_URL=https://app:8000
CALLBACK_BASE_URL=https://callback:8182

# SSL/TLS Configuration (self-signed certs for CI)
SSL_CERT_FILE=certs/cert.pem
SSL_KEY_FILE=certs/key.pem
CALLBACK_SSL_CERT_FILE=certs/callback_cert.pem
CALLBACK_SSL_KEY_FILE=certs/callback_key.pem

# CORS Configuration (HTTPS for production parity)
CORS_ORIGINS=https://app:8000,https://localhost:8000

# PostgreSQL Configuration
POSTGRES_DB=dashtam_test
POSTGRES_USER=dashtam_test_user
POSTGRES_PASSWORD=test_password
POSTGRES_PORT=5432
POSTGRES_INITDB_ARGS=-E UTF8 --lc-collate=C --lc-ctype=C

# Application Database Configuration
DATABASE_URL=postgresql+asyncpg://dashtam_test_user:test_password@postgres:5432/dashtam_test
DB_ECHO=false

# Redis Configuration (in-memory for CI)
REDIS_URL=redis://redis:6379/1
REDIS_PORT=6379

# Security Configuration (CI test keys - never use in production)
SECRET_KEY=ci-test-secret-key-never-use-in-production
ENCRYPTION_KEY=ci-test-encryption-key-32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# CI-specific flags
TESTING=true
CI=true
DISABLE_EXTERNAL_CALLS=true
MOCK_PROVIDERS=true
PYTHONUNBUFFERED=1

# Mock Provider Configuration for Testing
SCHWAB_API_KEY=mock_schwab_client_id
SCHWAB_API_SECRET=mock_schwab_client_secret
SCHWAB_API_BASE_URL=http://mock/schwab
SCHWAB_REDIRECT_URI=http://mock/callback

# Plaid Configuration (mocked)
PLAID_CLIENT_ID=mock_plaid_client_id
PLAID_SECRET=mock_plaid_secret
PLAID_ENVIRONMENT=sandbox

# Optional: Code coverage reporting
CODECOV_TOKEN=
EOF

echo "✅ Updated env/.env.ci"

echo ""
echo "🔐 Step 3: Update CI Docker Compose"

# Add cert volumes to docker-compose.ci.yml app service
# (Manual edit needed - see diff below)

echo ""
echo "🔐 Step 4: Update pytest fixtures"

# Add HTTPS fixtures to conftest.py
cat >> tests/conftest.py << 'EOF'

# ============================================
# HTTPS/SSL Fixtures for Test Environments
# ============================================

@pytest.fixture(scope="session")
def base_url_https():
    """Base URL for API tests (HTTPS in all environments)."""
    import os
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "testing":
        # Test environment - internal Docker hostname
        return "https://app:8000"
    else:
        # Development environment
        return "https://localhost:8000"


@pytest.fixture(scope="session", autouse=True)
def disable_ssl_warnings():
    """Disable SSL warnings for self-signed certs in test environments."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture
def http_client_https():
    """HTTP client configured for HTTPS with self-signed certs."""
    import httpx
    
    # Accept self-signed certs in test/dev environments
    return httpx.AsyncClient(verify=False)
EOF

echo "✅ Updated tests/conftest.py"

echo ""
echo "📝 Step 5: Manual edits required"
echo ""
echo "Please manually edit the following files:"
echo ""
echo "1. compose/docker-compose.ci.yml"
echo "   Add to app service volumes:"
echo "     - ../certs:/app/certs:ro"
echo ""
echo "   Add to callback service volumes:"
echo "     volumes:"
echo "       - ../certs:/app/certs:ro"
echo ""
echo "2. Verify certs are committed:"
echo "   git ls-files certs/"
echo ""
echo "After manual edits, run:"
echo "  git add ."
echo "  git commit -m 'feat(infra): enable SSL/TLS in test and CI environments'"
echo "  make test  # Verify all tests pass"
echo "  git push origin development"
```

---

## Testing & Verification Checklist

### Local Testing

- [ ] **Test Environment**:
  ```bash
  make test-up
  curl -k https://localhost:8001/health  # Should work
  make test  # All 305 tests should pass
  make test-down
  ```

- [ ] **CI Environment (Local)**:
  ```bash
  make ci-build
  make ci-test  # All 305 tests should pass
  make ci-down
  ```

### CI/CD Testing

- [ ] **Push to GitHub**:
  ```bash
  git push origin development
  ```

- [ ] **Monitor GitHub Actions**:
  - Check "Test Suite / Run Tests" passes
  - Check "Code Quality / lint" passes
  - Verify no SSL-related errors in logs

- [ ] **Review Logs**:
  - Search for "SSL" or "https" in CI logs
  - Verify uvicorn starts with HTTPS
  - Check for SSL warnings (should be minimal)

---

## Rollback Plan

If issues occur, rollback is simple:

```bash
# Revert changes
git revert HEAD

# Or manually restore old config
git checkout origin/development -- env/.env.test env/.env.ci compose/docker-compose.ci.yml tests/conftest.py

# Push
git push origin development
```

**Low Risk**: Changes are configuration-only, no code logic changes.

---

## Success Criteria

✅ **Test environment uses HTTPS**:
- `curl -k https://localhost:8001/health` works
- All 305 tests pass with HTTPS
- No SSL-related errors

✅ **CI environment uses HTTPS**:
- GitHub Actions tests pass
- CI logs show "Uvicorn running on https://..."
- No SSL-related failures

✅ **Production Parity Achieved**:
- Dev: HTTPS ✅
- Test: HTTPS ✅
- CI: HTTPS ✅

---

## Next Steps After Implementation

1. ✅ **Verify all environments use HTTPS** - Complete
2. ⏭️ **Move smoke tests to tests/smoke/** - Next task
3. ⏭️ **Add smoke tests to CI/CD** - Future task
4. ⏭️ **Convert smoke tests to pytest** - Future task (optional)

---

**END OF IMPLEMENTATION PLAN**
