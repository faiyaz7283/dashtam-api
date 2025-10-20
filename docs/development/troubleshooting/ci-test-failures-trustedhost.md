# CI Test Failures - TrustedHostMiddleware Issue

The Dashtam project CI pipeline experienced test failures where 19 out of 39 tests failed with 400 Bad Request errors in the CI environment, while all tests passed locally. After 1.5 hours of systematic debugging through six investigation phases, the root cause was identified as FastAPI's TrustedHostMiddleware blocking TestClient requests with hostname "testserver".

The investigation involved environment comparison, local reproduction of CI failures, dependency override attempts, and direct API testing. The solution was simple: adding "testserver" to the middleware's allowed_hosts list. This fixed all 39 tests in both local and CI environments.

**Duration**: ~1.5 hours | **Initial State**: 19/39 tests failing in CI | **Final State**: All 39 tests passing

---

## Table of Contents

- [Initial Problem](#initial-problem)
  - [Symptoms](#symptoms)
  - [Expected Behavior](#expected-behavior)
  - [Actual Behavior](#actual-behavior)
  - [Impact](#impact)
- [Investigation Steps](#investigation-steps)
  - [Step 1: Initial Discovery](#step-1-initial-discovery)
  - [Step 2: Environment Comparison](#step-2-environment-comparison)
  - [Step 3: Reproduction Attempt](#step-3-reproduction-attempt)
  - [Step 4: Dependency Override Investigation](#step-4-dependency-override-investigation)
  - [Step 5: Root Cause Discovery](#step-5-root-cause-discovery)
  - [Step 6: Shell Command Issues](#step-6-shell-command-issues)
- [Root Cause Analysis](#root-cause-analysis)
  - [Primary Cause](#primary-cause)
  - [Contributing Factors](#contributing-factors)
    - [Factor 1: Environment Configuration Differences](#factor-1-environment-configuration-differences)
    - [Factor 2: Complex Error Path](#factor-2-complex-error-path)
- [Solution Implementation](#solution-implementation)
  - [Approach](#approach)
  - [Changes Made](#changes-made)
    - [Change 1: src/main.py - TrustedHostMiddleware Configuration](#change-1-srcmainpy---trustedhostmiddleware-configuration)
  - [Implementation Steps](#implementation-steps)
- [Verification](#verification)
  - [Test Results](#test-results)
  - [Verification Steps](#verification-steps)
  - [Regression Testing](#regression-testing)
- [Lessons Learned](#lessons-learned)
  - [Technical Insights](#technical-insights)
  - [Process Improvements](#process-improvements)
  - [Best Practices](#best-practices)
- [Future Improvements](#future-improvements)
  - [Short-Term Actions](#short-term-actions)
  - [Long-Term Improvements](#long-term-improvements)
  - [Monitoring & Prevention](#monitoring--prevention)
- [References](#references)
- [Document Information](#document-information)

---

## Initial Problem

### Symptoms

**Environment:** CI/CD (GitHub Actions)

```bash
19/39 tests FAILED - 400 Bad Request errors
All tests passing in local development environment
```

**Working Environments:** Local dev, local test

### Expected Behavior

All 39 tests should pass in CI environment, matching local test results.

### Actual Behavior

19 API endpoint tests failed in CI with 400 Bad Request status codes, while identical tests passed in local environments.

### Impact

- **Severity:** High
- **Affected Components:** CI/CD pipeline, FastAPI TestClient, TrustedHostMiddleware
- **User Impact:** Blocked PR merges and deployments

## Investigation Steps

Systematic debugging through six phases over 1.5 hours.

### Step 1: Initial Discovery

**Hypothesis:** Tests might be hanging or timing out in CI environment.

**Investigation:**

1. Checked CI logs to understand test execution patterns
2. Identified that tests were completing (not hanging)
3. Found pattern: 19 API tests failing with 400 Bad Request
4. Noted key difference: Tests pass locally but fail in CI

```bash
# CI logs showed:
# 19/39 tests FAILED
# All failures: 400 Bad Request
```

**Findings:**

- Tests completing successfully but returning 400 status codes
- Only API endpoint tests failing (integration tests passing)
- Failure pattern consistent across all CI runs

**Result:** 🔍 Partial insight - environment-specific issue confirmed

### Step 2: Environment Comparison

**Hypothesis:** Configuration differences between local and CI environments causing failures.

**Investigation:**

Created detailed comparison document between local docker-compose and CI docker-compose configurations.

```bash
# Discovered differences:
# - Callback service missing in CI
# - Missing env vars: API_BASE_URL, CALLBACK_BASE_URL
# - Network configuration differences
```

**Findings:**

- Callback service was missing from CI compose file
- Critical environment variables not set in CI
- Added missing components and variables to CI configuration

**Result:** ❌ Not the cause - tests still failed after fixing these issues

### Step 3: Reproduction Attempt

**Hypothesis:** Running CI compose configuration locally would reproduce the failures.

**Investigation:**

Ran CI docker-compose configuration on local machine to enable faster debugging iteration.

```bash
docker-compose -f docker-compose.ci.yml up --abort-on-container-exit
# Result: Successfully reproduced failures locally
# Same 19 tests failing with same 400 errors
```

**Findings:**

- Issue is environment-specific, not CI-platform specific
- Can debug faster locally without waiting for CI pipeline
- Confirmed 19 tests fail identically in local CI config

**Result:** ✅ Issue reproduced - enables local debugging

### Step 4: Dependency Override Investigation

**Hypothesis:** Async/sync mismatch between FastAPI endpoints and test session causing issues.

**Investigation:**

Created AsyncToSyncWrapper to bridge async endpoints with sync test sessions:

```python
class AsyncToSyncWrapper:
    def __init__(self, async_session):
        self.async_session = async_session
    
    def add(self, obj):
        asyncio.run(self.async_session.add(obj))
    
    def commit(self):
        asyncio.run(self.async_session.commit())
```

Added missing methods (delete, etc.) as errors appeared. Fixed local tests but CI still failed.

**Findings:**

- Dependency override approach fixed some local test issues
- However, CI tests still returned 400 errors
- Root cause must be something else

**Result:** ❌ Not the cause - fixed symptoms but not root cause

### Step 5: Root Cause Discovery

**Hypothesis:** Testing API directly outside pytest framework might reveal actual error.

**Investigation:**

Used Python directly to test API, bypassing pytest:

```python
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)
response = client.get("/health")
print(response.status_code)  # 400
print(response.text)  # "Invalid host header"
```

**Findings:**

- Actual error message revealed: "Invalid host header"
- FastAPI's TrustedHostMiddleware blocking requests
- TestClient uses "testserver" as default Host header
- "testserver" not in allowed_hosts list

**Result:** ✅ Issue found - TrustedHostMiddleware configuration missing "testserver"

### Step 6: Shell Command Issues

**Hypothesis:** CI execution environment has shell compatibility issues.

**Investigation:**

Encountered exit code 127 (command not found) errors in CI:

```bash
# Issue 1: Unicode/emoji characters in echo statements breaking
echo "✅ Tests complete"  # Failed with exit 127

# Issue 2: Multi-line command continuation breaking
docker-compose exec app \
  uv run pytest  # Failed with parsing errors
```

**Findings:**

- Unicode characters in shell commands cause CI failures
- Multi-line command continuation unreliable in CI
- Simplified to single-line commands fixed execution

**Result:** ✅ Fixed - simplified shell commands for CI compatibility

## Root Cause Analysis

### Primary Cause

**Problem:** FastAPI's TrustedHostMiddleware was blocking TestClient requests

FastAPI's `TrustedHostMiddleware` validates the `Host` header in incoming requests. When using `TestClient` for testing, the default hostname is "testserver". However, the middleware's `allowed_hosts` configuration did not include "testserver", causing all TestClient requests to be rejected with 400 Bad Request.

```python
# Problematic configuration
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "app"]  # Missing "testserver"!
)
```

**Why This Happens:**

- TestClient uses "testserver" as default Host header value
- TrustedHostMiddleware validates Host against allowed_hosts list
- "testserver" not in list → 400 Bad Request response
- Local Docker testing worked because containers use "app" as hostname
- CI environment behavior differed from local Docker setup

**Impact:**

All API tests using TestClient failed in CI, while integration tests accessing database directly passed. This blocked PR merges and CI/CD pipeline.

### Contributing Factors

#### Factor 1: Environment Configuration Differences

CI environment initially missing critical environment variables (`API_BASE_URL`, `CALLBACK_BASE_URL`) which masked the real issue and led investigation down wrong paths.

#### Factor 2: Complex Error Path

Initial investigation focused on dependency injection and async/sync mismatches, delaying discovery of simpler root cause. 400 Bad Request status code didn't immediately point to Host header validation issue.

## Solution Implementation

### Approach

After systematic debugging through six investigation phases, the solution was identified as adding "testserver" to the TrustedHostMiddleware allowed_hosts list. This simple one-line change fixed all 39 tests in both local and CI environments.

### Changes Made

#### Change 1: src/main.py - TrustedHostMiddleware Configuration

**Before:**

```python
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "app"]
)
```

**After:**

```python
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "app", "testserver"]  # Added testserver
)
```

**Rationale:**

TestClient uses "testserver" as the default Host header. Adding it to allowed_hosts permits TestClient requests while maintaining security for production. In production, the allowed_hosts list should be configured via environment variables to only include actual production domains.

### Implementation Steps

1. **Identified the issue through direct API testing**

   ```bash
   python -c "from fastapi.testclient import TestClient; from src.main import app; client = TestClient(app); print(client.get('/health').text)"
   # Output: "Invalid host header"
   ```

2. **Updated TrustedHostMiddleware configuration**

   Added "testserver" to allowed_hosts list in src/main.py

3. **Verified locally with CI docker-compose configuration**

   ```bash
   docker-compose -f docker-compose.ci.yml up --abort-on-container-exit
   # Result: All 39 tests passing ✅
   ```

4. **Pushed to CI and verified in GitHub Actions**

   ```bash
   git push origin branch-name
   # Result: All 39 tests passing in CI ✅
   ```

## Verification

### Test Results

**Before Fix:**

```bash
CI: 19/39 tests FAILED (48% failure rate)
Local: 39/39 tests PASSED
Local CI config: 19/39 tests FAILED (reproduced issue)
```

**After Fix:**

```bash
CI: 39/39 tests PASSED ✅
Local: 39/39 tests PASSED ✅
Local CI config: 39/39 tests PASSED ✅
```

### Verification Steps

1. **Test in local CI configuration**

   ```bash
   docker-compose -f docker-compose.ci.yml up --abort-on-container-exit --exit-code-from app
   ```

   **Result:** ✅ All 39 tests passing

2. **Test in GitHub Actions CI/CD**

   Pushed changes and monitored GitHub Actions workflow.

   **Result:** ✅ All 39 tests passing

3. **Verify in all environments**

   - Dev: ✅ 39/39 passing
   - Test: ✅ 39/39 passing
   - CI: ✅ 39/39 passing

### Regression Testing

All existing tests maintained functionality. No regressions introduced by the fix. Verified that:

- API endpoints still accessible in all environments
- Security middleware still functioning correctly
- TestClient works in all test scenarios
- No performance impact from configuration change

## Lessons Learned

### Technical Insights

1. **TestClient uses "testserver" hostname**

   FastAPI's TestClient defaults to "testserver" as Host header value. This must be added to TrustedHostMiddleware allowed_hosts when using the middleware.

2. **TrustedHostMiddleware blocks unknown hosts strictly**

   Security middleware validates Host header against allowed list. No exceptions, even for testing.

3. **Read complete error messages early**

   Reading full error details (not just status codes) reveals root cause faster. "Invalid host header" message immediately pointed to solution.

4. **Environment parity matters**

   Small configuration differences between local and CI environments can cause mysterious failures. Systematic comparison is essential.

5. **Direct API testing bypasses frameworks**

   Testing API directly outside pytest revealed actual error message that pytest was hiding or truncating.

### Process Improvements

1. **Test directly outside framework first**

   When tests fail mysteriously, test API directly with minimal framework involvement. This revealed "Invalid host header" error immediately.

2. **Read complete error messages**

   Don't stop at HTTP status codes. Read full response text and error details to understand root cause.

3. **Start with simple hypotheses**

   Check configuration and setup before investigating complex async/dependency injection solutions. Simpler explanations are more likely.

4. **Document debugging steps systematically**

   Recording each investigation phase with hypothesis, findings, and results helps track progress and prevents circular investigation.

5. **Reproduce CI failures locally**

   Local reproduction enables faster debugging iteration without waiting for CI pipeline runs.

### Best Practices

- Always include "testserver" in TrustedHostMiddleware allowed_hosts when using TestClient
- Reproduce CI failures locally before debugging in CI pipeline
- Use systematic environment comparison when tests pass locally but fail in CI
- Test APIs directly outside test framework when debugging mysterious failures
- Document complete error messages, not just status codes
- Create health checks that verify TestClient can access API endpoints

## Future Improvements

### Short-Term Actions

1. **Add Makefile commands for CI debugging**

   **Timeline:** Next sprint

   **Owner:** DevOps

   Commands to add: ci-test, ci-build, ci-clean, ci-up, ci-down, ci-logs for easier CI environment debugging.

2. **Document TestClient behavior**

   **Timeline:** Complete

   **Owner:** Done - see testing documentation

   Added documentation about TestClient's "testserver" hostname and middleware interactions.

### Long-Term Improvements

1. **Environment configuration validation**

   Add automated checks to verify critical environment variables are set in all environments. Prevent deployment if configuration is incomplete.

2. **CI debugging toolkit**

   Create helper scripts/commands for common CI debugging tasks. Include commands for local CI reproduction, log analysis, and environment comparison.

### Monitoring & Prevention

Add health check that verifies TestClient can access API endpoints:

```python
# tests/test_health.py
def test_testclient_can_access_api(client: TestClient):
    """Verify TestClient is not blocked by middleware."""
    response = client.get("/health")
    assert response.status_code == 200, f"TestClient blocked: {response.text}"
```

This test will fail immediately if TrustedHostMiddleware configuration breaks TestClient access, preventing future incidents.

## References

**Related Documentation:**

- [Docker Setup](../infrastructure/docker-setup.md) - Environment configuration
- [CI/CD Documentation](../infrastructure/ci-cd.md) - Pipeline setup
- [Testing Guide](../../testing/guide.md) - TestClient usage

**External Resources:**

- [FastAPI TrustedHostMiddleware](https://fastapi.tiangolo.com/advanced/middleware/#trustedhostmiddleware) - Official documentation
- [TestClient Documentation](https://fastapi.tiangolo.com/tutorial/testing/) - TestClient behavior
- [GitHub Actions Debugging](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/about-monitoring-and-troubleshooting) - CI debugging guide

**Related Issues:**

- GitHub PR - Phase 3 test fixes
- CI/CD pipeline configuration updates

---

## Document Information

**Template:** [troubleshooting-template.md](../../templates/troubleshooting-template.md)
**Created:** 2025-10-02
**Last Updated:** 2025-10-20
