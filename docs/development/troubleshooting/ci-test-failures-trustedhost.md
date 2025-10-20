# CI Test Failures - TrustedHostMiddleware Issue

**Date:** 2025-10-02
**Issue:** 19/39 tests failing in CI environment with 400 Bad Request, all passing locally
**Resolution:** Added "testserver" to TrustedHostMiddleware allowed_hosts configuration
**Status:** ✅ RESOLVED

---

## Executive Summary

The Dashtam project CI pipeline experienced test failures where 19 out of 39 tests failed with 400 Bad Request errors in the CI environment, while all tests passed locally. After 1.5 hours of systematic debugging through six investigation phases, the root cause was identified as FastAPI's TrustedHostMiddleware blocking TestClient requests with hostname "testserver".

The investigation involved environment comparison, local reproduction of CI failures, dependency override attempts, and direct API testing. The solution was simple: adding "testserver" to the middleware's allowed_hosts list. This fixed all 39 tests in both local and CI environments.

**Duration**: ~1.5 hours
**Initial State**: 19/39 tests failing in CI, all passing locally
**Final State**: All 39 tests passing in both environments

---

## Table of Contents

1. [Initial Problem](#initial-problem)
2. [Investigation Steps](#investigation-steps)
   - [Phase 1: Initial Discovery](#phase-1-initial-discovery-10-mins)
   - [Phase 2: Environment Comparison](#phase-2-environment-comparison-20-mins)
   - [Phase 3: Reproduction Attempt](#phase-3-reproduction-attempt-15-mins)
   - [Phase 4: Dependency Override Investigation](#phase-4-dependency-override-investigation-30-mins)
   - [Phase 5: Root Cause Discovery](#phase-5-root-cause-discovery-15-mins)
   - [Phase 6: Shell Command Issues](#phase-6-shell-command-issues-20-mins)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Solution Implementation](#solution-implementation)
5. [Verification](#verification)
6. [Lessons Learned](#lessons-learned)
7. [Future Improvements](#future-improvements)
8. [References](#references)

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

---

## Investigation Steps

Systematic debugging through six phases over 1.5 hours.

### Phase 1: Initial Discovery (10 mins)

**Objective**: Understand the scope of the problem

1. **Checked CI logs** → Found tests were completing but failing (not hanging)
2. **Identified pattern**: 19 API tests failing with 400 Bad Request
3. **Key insight**: Tests pass locally but fail in CI

**Approach**: Start with log analysis to understand failure patterns

### Phase 2: Environment Comparison (20 mins)

**Objective**: Find differences between working and failing environments

1. **Created detailed comparison document** (`DOCKER_COMPOSE_COMPARISON.md`)
2. **Discovered missing components**:
   - Callback service missing in CI
   - Critical environment variables missing (`API_BASE_URL`, `CALLBACK_BASE_URL`)
3. **Fixed these issues** but tests still failed

**Approach**: Systematic comparison of configuration files

### Phase 3: Reproduction Attempt (15 mins)

**Objective**: Reproduce CI failures locally

1. **Ran CI compose locally** → Successfully reproduced failures
2. **Confirmed**: Issue is environment-specific, not CI-platform specific
3. **Key finding**: Same 19 tests fail with same error locally when using CI config

**Approach**: Local reproduction to enable faster iteration

### Phase 4: Dependency Override Investigation (30 mins)

**Objective**: Fix async/sync mismatch issues

1. **Initial hypothesis**: Dependency overrides not working
2. **Created AsyncToSyncWrapper** to bridge async endpoints with sync test sessions
3. **Added missing methods** (`delete`, etc.) as discovered
4. **Result**: Fixed local tests but CI still failed

**Approach**: Incremental fixes based on specific error messages

### Phase 5: Root Cause Discovery (15 mins)

**Objective**: Find why dependency overrides don't work in CI

1. **Breakthrough moment**: Tested API directly with Python
2. **Discovered actual error**: "Invalid host header"
3. **Found culprit**: TrustedHostMiddleware blocking "testserver"
4. **Simple fix**: Added "testserver" to allowed_hosts

**Approach**: Direct API testing outside of pytest framework

### Phase 6: Shell Command Issues (20 mins)

**Objective**: Fix CI execution errors

1. **Exit code 127**: Command not found errors
2. **Issue 1**: Unicode/emoji characters in echo statements
3. **Issue 2**: Multi-line command continuation breaking
4. **Solution**: Simplified to single-line command

**Approach**: Iterative simplification of shell commands

---

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
- "testserver" not in list → 400 Bad Request
- Local testing worked because Docker containers use "app" as hostname
- CI environment behavior differed from local Docker setup

**Impact:**

All API tests using TestClient failed in CI, while integration tests accessing database directly passed.

### Contributing Factors

#### Factor 1: Environment Configuration Differences

CI environment missing critical environment variables (`API_BASE_URL`, `CALLBACK_BASE_URL`) which masked the real issue initially.

#### Factor 2: Complex Error Path

Initial investigation focused on dependency injection and async/sync mismatches, delaying discovery of simpler root cause.

---

## Solution Implementation

### Approach

After systematic debugging, the solution was to add "testserver" to the TrustedHostMiddleware allowed_hosts list.

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

TestClient uses "testserver" as the default Host header. Adding it to allowed_hosts permits TestClient requests while maintaining security for production.

### Implementation Steps

1. **Identified the issue** through direct API testing with Python

   ```bash
   python -c "from fastapi.testclient import TestClient; ..."
   ```

   Result: "Invalid host header" error revealed

2. **Updated TrustedHostMiddleware configuration** to include "testserver"

3. **Verified locally** with CI docker-compose configuration

   ```bash
   docker-compose -f docker-compose.ci.yml up --abort-on-container-exit
   ```

   Result: All 39 tests passing

4. **Pushed to CI** and verified in GitHub Actions

   Result: All 39 tests passing in CI

---

## Verification

### Test Results

**Before Fix:**

```bash
CI: 19/39 tests FAILED (48% failure rate)
Local: 39/39 tests PASSED
```

**After Fix:**

```bash
CI: 39/39 tests PASSED ✅
Local: 39/39 tests PASSED ✅
```

### Verification Steps

1. **Tested in local CI configuration**

   ```bash
   docker-compose -f docker-compose.ci.yml up --abort-on-container-exit --exit-code-from app
   ```

   **Result:** ✅ All 39 tests passing

2. **Tested in GitHub Actions CI/CD**

   **Result:** ✅ All 39 tests passing

3. **Verified in all environments**

   - Dev: ✅ 39/39 passing
   - Test: ✅ 39/39 passing
   - CI: ✅ 39/39 passing

### Regression Testing

All existing tests maintained functionality. No regressions introduced by the fix.

---

## Lessons Learned

### Technical Insights

1. **TestClient uses "testserver" hostname**: FastAPI's TestClient defaults to "testserver" as Host header
2. **TrustedHostMiddleware blocks unknown hosts**: Security middleware validates Host header strictly
3. **Check actual error messages early**: Reading full error details reveals root cause faster
4. **Environment parity matters**: CI and local differences require careful investigation

### Debugging Methodology Analysis

### What Worked Well

1. **Systematic comparison** of environments
2. **Local reproduction** of CI issues
3. **Direct testing** outside test framework
4. **Incremental fixes** with verification
5. **Clear documentation** of findings

### Process Improvements

1. **Test directly outside framework first**: Direct API testing revealed root cause immediately
2. **Read complete error messages**: Don't stop at status codes, read full error details
3. **Start with simple hypotheses**: Check configuration before complex async/dependency solutions
4. **Document debugging steps**: Systematic documentation helped track progress

### Best Practices

- Always include "testserver" in TrustedHostMiddleware allowed_hosts for testing
- Reproduce CI failures locally before debugging
- Use systematic environment comparison when tests pass locally but fail in CI
- Document command usage patterns for future Makefile improvements

---

## Future Improvements

### Short-Term Actions

1. **Add Makefile commands for CI debugging**

   **Timeline:** Next sprint

   **Owner:** DevOps

   Commands identified: ci-test, ci-build, ci-clean, gh-status, gh-watch

2. **Document TestClient behavior**

   **Timeline:** Complete

   **Owner:** Done - see testing documentation

### Long-Term Improvements

1. **Environment configuration validation**

   Add automated checks to verify critical env vars are set in all environments

2. **CI debugging toolkit**

   Create helper scripts/commands for common CI debugging tasks

### Monitoring & Prevention

Add health check that verifies TestClient can access API endpoints:

```python
# tests/test_health.py
def test_testclient_can_access_api(client: TestClient):
    """Verify TestClient is not blocked by middleware."""
    response = client.get("/health")
    assert response.status_code == 200, "TestClient blocked by middleware"
```

---

## References

**Related Documentation:**

- [Docker Setup](../infrastructure/docker-setup.md) - Environment configuration
- [CI/CD Documentation](../infrastructure/ci-cd.md) - Pipeline setup
- [Testing Guide](../testing/guide.md) - TestClient usage

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
**Last Updated:** 2025-10-17
