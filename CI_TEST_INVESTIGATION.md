# CI Test Failures Investigation Summary

## Current Status

### Test Results
- **Local with `make test` (docker-compose.test.yml)**: ✅ 39 tests pass
- **CI with GitHub Actions (docker-compose.ci.yml)**: ❌ 19 tests fail (all with 400 Bad Request)  
- **Local with CI compose**: ❌ 19 tests fail (reproduces CI issue locally)

## Root Cause Analysis

### The Problem
19 API tests fail with 400 Bad Request in CI but pass locally. The failures are consistent and all relate to endpoints that require authentication or database access.

### Key Differences Found

1. **Docker Compose Differences**:
   - ✅ Fixed: Missing callback service in CI 
   - ✅ Fixed: Missing API_BASE_URL and CALLBACK_BASE_URL environment variables
   - ⚠️ Different volume mounts: CI uses `:ro` (read-only), test uses `:rw`
   - ⚠️ Different initialization: CI runs `init_test_db.py`, test doesn't

2. **Test Execution Differences**:
   - Test env: Container stays running, tests executed via `docker exec`
   - CI env: Container starts, runs tests immediately, then exits
   - This may affect how fixtures and database connections are initialized

3. **Dependency Override Issue**:
   - Created `AsyncToSyncWrapper` to bridge async endpoints with sync test sessions
   - Works in test environment but appears not to work in CI
   - The 400 errors suggest the dependency overrides aren't being applied

## What We Fixed

1. ✅ Added callback service to CI compose
2. ✅ Added missing environment variables to CI
3. ✅ Created AsyncToSyncWrapper for proper async/sync bridging
4. ✅ Fixed code formatting issues

## What's Still Broken

The dependency overrides in `tests/conftest.py` aren't being applied properly in the CI environment, causing:
- `get_current_user` dependency to fail (returns 400)
- `get_session` dependency to fail (returns 400)

## Hypothesis

The CI environment's test database initialization or fixture setup is different from the local test environment. Specifically:

1. The `db` fixture may not be creating a proper synchronous session in CI
2. The fixture scoping may be causing issues (session vs module scope)
3. The `init_test_db.py` script run by CI may be interfering with test fixtures

## Recommended Next Steps

### Option 1: Make CI Match Test Environment Exactly
1. Remove `init_test_db.py` from CI command
2. Make CI container stay running like test container
3. Execute tests the same way as test environment

### Option 2: Debug Why Overrides Don't Work in CI
1. Add logging to confirm dependency overrides are being applied
2. Check if the `db` fixture is properly initialized in CI
3. Verify the TestClient is using the overridden dependencies

### Option 3: Unified Testing Approach
1. Create a single consistent test execution method
2. Use the same initialization for both environments
3. Ensure fixtures work identically regardless of environment

## Immediate Action Items

1. **Verify fixture initialization**: Add debug logging to conftest.py to confirm fixtures are created
2. **Check database connection**: Ensure the sync test database is properly set up in CI
3. **Test with simplified override**: Try a minimal dependency override to isolate the issue
4. **Consider async test approach**: If sync approach continues to fail, consider migrating to async tests

## Key Learning

The test infrastructure must be **environment-agnostic**. Tests should pass identically whether run via:
- `make test` (local test environment)
- `docker-compose -f docker-compose.ci.yml` (CI environment)
- GitHub Actions CI pipeline

The current setup has environment-specific behavior that makes debugging difficult and reduces confidence in test results.