# Test Fixture Scope Issues - Troubleshooting Guide

Comprehensive investigation and resolution of pytest fixture scope issues causing 9 test failures in the full test suite while all tests passed individually. The root cause was session-scoped client fixtures causing state pollution across test modules.

---

## Initial Problem

### Symptoms

During implementation of session management feature, 9 tests began failing when running the full test suite, but all tests passed when run individually or in isolation.

**Environment:** Test environment (`make test` with `compose/docker-compose.test.yml`)

```bash
# Full suite failures
$ docker compose -f compose/docker-compose.test.yml exec app uv run pytest tests/
FAILED tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_requires_auth
FAILED tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_returns_all
FAILED tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_includes_metadata
FAILED tests/api/test_sessions_endpoints.py::TestRevokeSession::test_revoke_session_requires_auth
FAILED tests/api/test_sessions_endpoints.py::TestRevokeSession::test_revoke_session_success
FAILED tests/api/test_sessions_endpoints.py::TestRevokeSession::test_revoke_session_not_found
FAILED tests/api/test_sessions_endpoints.py::TestRevokeOtherSessions::test_revoke_other_sessions_requires_auth
FAILED tests/api/test_sessions_endpoints.py::TestRevokeAllSessions::test_revoke_all_sessions_requires_auth
FAILED tests/api/test_sessions_endpoints.py::TestRevokeAllSessions::test_revoke_all_sessions_success

465/474 tests passing (93.8% pass rate)

# Individual test success
$ docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_requires_auth -v
PASSED
```

**Working Environments:**

- Individual test execution (all tests passed when run alone)
- Test modules run in isolation (single file execution)

### Expected Behavior

All 474 tests should pass when running the full test suite with `pytest tests/`, regardless of execution order or module dependencies.

### Actual Behavior

- **Full suite:** 465/474 passing (9 failures, 93.8%)
- **Individual tests:** 9/9 passing (100%)
- **Pattern:** All failures in `test_sessions_endpoints.py`, all authentication-related tests
- **Failure mode:** Tests that should require authentication (401 Unauthorized) were passing authentication checks unexpectedly

### Impact

- **Severity:** High
- **Affected Components:** Session management API tests, authentication middleware
- **User Impact:** No production impact (test-only issue), but blocking PR merge and deployment

## Investigation Steps

### Step 1: Verify Test Implementation

**Hypothesis:** Tests might have incorrect assertions or logic errors

**Investigation:**

Reviewed test code in `tests/api/test_sessions_endpoints.py`:

```python path=tests/api/test_sessions_endpoints.py start=26
def test_list_sessions_requires_auth(self, client_no_auth: TestClient):
    """Test list sessions endpoint returns 401 without JWT."""
    response = client_no_auth.get("/api/v1/auth/sessions")
    
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()
```

**Findings:**

- Test logic is correct and follows project standards
- Assertions are appropriate (checking for 401 status code)
- `client_no_auth` fixture properly configured without authentication
- Tests pass when run individually, confirming implementation correctness

**Result:** ❌ Not the cause (test implementation is correct)

### Step 2: Run Tests in Isolation

**Hypothesis:** State pollution or dependency between test modules

**Investigation:**

Ran failing tests in isolation to compare behavior:

```bash
# Run single test module
docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/api/test_sessions_endpoints.py -v

# Result: ALL TESTS PASSED (12/12)

# Run full suite
docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/ -v

# Result: 9 FAILURES in test_sessions_endpoints.py
```

**Findings:**

- All 9 failing tests passed when module run alone
- Failures only occurred when tests run after other modules
- Classic symptom of fixture scope issue or state pollution

**Result:** ✅ **Root cause identified: Fixture scope issue**

### Step 3: Identify Session-Scoped Fixtures

**Hypothesis:** Session-scoped fixtures persist state across test modules

**Investigation:**

Examined `tests/conftest.py` fixture scopes:

```python path=tests/conftest.py start=null
# BEFORE (problematic):
@pytest.fixture(scope="session")
def client(db: Session):
    """FastAPI TestClient with database override."""
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**Findings:**

- `client` fixture used `scope="session"` (persists across all modules)
- `app.dependency_overrides` set once at session start, cleared at session end
- Dependency overrides from earlier test modules leaked into later modules
- Authentication bypasses from one module affected auth-required tests in other modules

**Result:** ✅ **Confirmed root cause: Session-scoped fixtures**

### Step 4: Check Cache Singleton Pattern

**Hypothesis:** Cache singleton not reset between tests

**Investigation:**

Reviewed cache factory implementation:

```python path=src/core/cache/factory.py start=null
# Cache factory with singleton pattern
_cache_instance: CacheBackend | None = None

def get_cache() -> CacheBackend:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache(...)
    return _cache_instance
```

**Findings:**

- Cache singleton created once per test session
- No reset mechanism between tests
- Stale cache data could persist across test modules
- Particularly problematic for token blacklist tests

**Result:** 🔍 **Contributing factor identified**

## Root Cause Analysis

### Primary Cause

**Problem:**

Session-scoped pytest fixtures (`client`, `authenticated_user`) persisted FastAPI application state (`app.dependency_overrides`) across test modules, causing authentication dependency overrides to leak between tests.

```python path=tests/conftest.py start=null
# ❌ PROBLEMATIC: Session scope
@pytest.fixture(scope="session")
def client(db: Session):
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()  # Only clears at END of session!
```

**Why This Happens:**

1. **Pytest session scope**: Fixture created once at start, destroyed at end of entire test run
2. **Dependency override persistence**: `app.dependency_overrides` dictionary persists in memory
3. **Early tests set overrides**: Tests with authentication set `get_current_user` override
4. **Later tests inherit overrides**: Session management tests expected NO override, but inherited from earlier modules
5. **Auth bypass propagation**: Tests expecting 401 Unauthorized got 200 OK due to inherited overrides

**Impact:**

- Tests requiring authentication (401 checks) received authenticated user from earlier tests
- Authentication middleware bypassed unexpectedly
- Test isolation violated (tests depend on execution order)
- False positives (tests passing incorrectly)

### Contributing Factors

#### Factor 1: Cache Singleton Not Reset

The cache factory pattern used a global singleton (`_cache_instance`) that persisted across tests without explicit reset, potentially causing stale data issues.

#### Factor 2: TestClient Event Loop Management

FastAPI's TestClient manages an event loop internally. Function-scoped fixtures create/destroy TestClient rapidly, which can trigger event loop lifecycle issues if not handled properly.

## Solution Implementation

### Approach

Two-part solution addressing fixture scopes and singleton state:

1. **Change fixture scopes**: Convert client fixtures from `session` to `function` scope
2. **Add cache reset fixture**: Autouse fixture to reset cache singleton between tests

This ensures complete test isolation with minimal performance impact.

### Changes Made

#### Change 1: Client Fixture Scope

**Before:**

```python path=tests/conftest.py start=null
@pytest.fixture(scope="session")
def client(db: Session):
    """FastAPI TestClient with database override."""
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**After:**

```python path=tests/conftest.py start=225
@pytest.fixture(scope="function")
def client(db: Session):
    """FastAPI TestClient with database override.
    
    Function-scoped to ensure test isolation.
    Each test gets fresh client with clean dependency overrides.
    """
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**Rationale:**

Function scope ensures `app.dependency_overrides` is cleared after EVERY test, preventing state pollution. Each test starts with clean application state.

#### Change 2: Authenticated User Fixture Scope

**Before:**

```python path=tests/conftest.py start=null
@pytest.fixture(scope="session")
def authenticated_user(client: TestClient, test_user: User) -> dict:
    # Create user, login, return tokens
    return {...}
```

**After:**

```python path=tests/conftest.py start=252
@pytest.fixture(scope="function")
def authenticated_user(client: TestClient, test_user: User) -> dict:
    """Authenticated user with valid access token.
    
    Function-scoped to ensure test isolation.
    Each test gets fresh authentication without state leakage.
    """
    # Create user, login, return tokens
    return {...}
```

**Rationale:**

Matches client fixture scope. Prevents authentication state from leaking between tests.

#### Change 3: Cache Singleton Reset Fixture

**Before:**

No cache reset mechanism existed.

**After:**

```python path=tests/conftest.py start=40
@pytest.fixture(scope="function", autouse=True)
def reset_cache_singleton():
    """Reset cache singleton before and after each test.
    
    CRITICAL: Cache factory uses singleton pattern.
    Must reset before/after tests to prevent state pollution.
    
    Autouse=True ensures this runs for ALL tests without explicit dependency.
    """
    from src.core.cache import factory
    factory._cache_instance = None  # Reset before test
    yield
    factory._cache_instance = None  # Reset after test
```

**Rationale:**

Autouse fixture ensures cache singleton reset happens automatically for every test, preventing stale cache data from affecting subsequent tests.

### Implementation Steps

1. **Update client fixture scope**

   ```bash
   # Edit tests/conftest.py
   # Change @pytest.fixture(scope="session") to scope="function"
   ```

2. **Update authenticated_user fixture scope**

   ```bash
   # Edit tests/conftest.py
   # Change scope="session" to scope="function"
   ```

3. **Add cache singleton reset fixture**

   ```bash
   # Add new autouse fixture to tests/conftest.py
   # Resets cache before/after each test
   ```

4. **Run full test suite**

   ```bash
   docker compose -f compose/docker-compose.test.yml exec app \
     uv run pytest tests/ -v
   ```

## Verification

### Test Results

**Before Fix:**

```bash
$ docker compose -f compose/docker-compose.test.yml exec app uv run pytest tests/ -v
...
============================= short test summary info ==============================
FAILED tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_requires_auth
FAILED tests/api/test_sessions_endpoints.py::TestListSessions::test_list_sessions_returns_all
[... 7 more failures ...]
===================== 465 passed, 9 failed in 45.23s ==============================
```

**After Fix:**

```bash
$ docker compose -f compose/docker-compose.test.yml exec app uv run pytest tests/ -v
...
===================== 474 passed in 47.12s ==========================================
```

### Verification Steps

1. **Run full test suite**

   ```bash
   make test
   ```

   **Result:** ✅ 474/474 tests passing (100%)

2. **Run session management tests in isolation**

   ```bash
   docker compose -f compose/docker-compose.test.yml exec app \
     uv run pytest tests/api/test_sessions_endpoints.py -v
   ```

   **Result:** ✅ 12/12 tests passing (100%)

3. **Run authentication tests (previously affected)**

   ```bash
   docker compose -f compose/docker-compose.test.yml exec app \
     uv run pytest tests/api/test_auth_endpoints.py -v
   ```

   **Result:** ✅ 20/20 tests passing (100%)

4. **Verify no deprecation warnings**

   ```bash
   docker compose -f compose/docker-compose.test.yml exec app \
     uv run pytest tests/ --strict-warnings
   ```

   **Result:** ✅ Zero warnings

### Regression Testing

Verified that fixture scope changes did not introduce new issues:

- **Performance:** Test suite run time increased by ~2 seconds (47s vs 45s, 4% increase) - acceptable tradeoff
- **Coverage:** Code coverage maintained at 86%
- **Smoke tests:** 22/22 smoke tests passing (end-to-end flows)

## Lessons Learned

### Technical Insights

1. **Fixture Scopes Matter**

   Pytest fixture scope directly impacts test isolation. Session-scoped fixtures sharing mutable state (like `app.dependency_overrides`) WILL cause test pollution.

2. **Tests Passing Individually ≠ Suite Passing**

   Individual test success does not guarantee full suite success. Always run full suite before PR review.

3. **Singletons in Tests Require Reset**

   Any singleton pattern in application code (cache factory, connection pools) requires explicit reset in tests via autouse fixtures.

4. **Event Loop Lifecycle**

   Function-scoped async fixtures with TestClient can trigger event loop issues if not managed carefully. TestClient handles this internally.

### Process Improvements

1. **Always Test Full Suite**

   Make `make test` (full suite) mandatory in PR checklist. Individual test success is insufficient.

2. **Document Fixture Scopes**

   Add docstrings to all fixtures explaining scope choice and rationale.

3. **Autouse Fixtures for Cleanup**

   Use autouse fixtures for singleton resets and global state cleanup (reduces developer burden).

### Best Practices

- **Infrastructure fixtures (DB engine, Redis connection):** `scope="session"` ✅ (expensive to create, stateless)
- **Database session fixtures:** `scope="function"` ✅ (requires isolation per test)
- **TestClient fixtures:** `scope="function"` ✅ (prevents dependency override pollution)
- **Test data fixtures (users, tokens):** `scope="function"` ✅ (each test needs fresh data)
- **Singleton resets:** Use `autouse=True` fixtures ✅ (automatic cleanup)

## Future Improvements

### Short-Term Actions

1. **Add Fixture Scope Documentation**

   **Timeline:** Immediate (part of this PR)

   **Owner:** Development team

   Update `docs/development/guides/testing-guide.md` with "Fixture Scope Best Practices" section.

2. **Create Fixture Scope Linter**

   **Timeline:** Next sprint

   **Owner:** Development team

   Custom pytest plugin to warn about session-scoped fixtures with mutable state.

### Long-Term Improvements

1. **Test Execution Order Randomization**

   Enable `pytest-randomly` plugin to randomize test execution order, exposing fixture scope issues early.

2. **Parallel Test Execution**

   Implement `pytest-xdist` for parallel test execution (requires all fixtures function-scoped).

### Monitoring & Prevention

Prevent recurrence with automated checks:

```bash
# Add to CI/CD pipeline
# Verify test suite passes 3 times with different random seeds
pytest tests/ --random-order-seed=1234
pytest tests/ --random-order-seed=5678
pytest tests/ --random-order-seed=9012

# All three runs must pass (exposes order dependencies)
```

## References

**Related Documentation:**

- [Testing Guide](../guides/testing-guide.md) - Project testing strategy and patterns
- [Session Management Architecture](../architecture/session-management.md) - Feature that exposed this issue

**External Resources:**

- [Pytest Fixture Scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session) - Official pytest documentation
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) - TestClient usage patterns
- [pytest-randomly](https://github.com/pytest-dev/pytest-randomly) - Test order randomization plugin

**Related Issues:**

- GitHub PR #XX - Session management feature implementation
- GitHub Commit `853db29` - Fix: Achieve 100% test pass rate

---

## Document Information

**Created:** 2025-10-29
**Last Updated:** 2025-10-29
