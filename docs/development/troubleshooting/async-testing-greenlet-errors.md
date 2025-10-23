# Async Testing Greenlet Errors - Troubleshooting Guide

The Dashtam project encountered persistent `MissingGreenlet` errors when implementing async testing patterns with pytest-asyncio 1.2.0, SQLAlchemy 2.0.43, and asyncpg. Despite following official documentation and implementing five different approaches (session-scoped event loops, NullPool configurations, transaction wrapping, savepoints, and clean sessions), all attempts resulted in greenlet context errors.

After extensive investigation, the root cause was identified as incompatibilities between asyncpg's event loop requirements, SQLAlchemy's greenlet bridge, and pytest-asyncio's fixture management. The solution was to adopt the synchronous testing pattern recommended by the FastAPI official template, using TestClient with synchronous Session objects. This eliminated all async complexity while maintaining full test coverage.

**Key Decision**: Synchronous testing (def test_*, not async def) with FastAPI TestClient (matches FastAPI official pattern)

---

## Table of Contents

- [Initial Problem](#initial-problem)
  - [Symptoms](#symptoms)
  - [Expected Behavior](#expected-behavior)
  - [Actual Behavior](#actual-behavior)
  - [Impact](#impact)
- [Investigation Steps](#investigation-steps)
  - [Step 1: Session-Scoped Event Loop with Pooled Connections](#step-1-session-scoped-event-loop-with-pooled-connections)
  - [Step 2: NullPool with Session-Scoped Async Fixtures](#step-2-nullpool-with-session-scoped-async-fixtures)
  - [Step 3: NullPool with Manual Transaction Wrapping](#step-3-nullpool-with-manual-transaction-wrapping)
  - [Step 4: Nested Transactions with Savepoints](#step-4-nested-transactions-with-savepoints)
  - [Step 5: Clean Session Without Transaction Wrapping](#step-5-clean-session-without-transaction-wrapping)
- [Root Cause Analysis](#root-cause-analysis)
  - [Primary Cause](#primary-cause)
  - [Contributing Factors](#contributing-factors)
    - [Factor 1: Official Documentation Gaps](#factor-1-official-documentation-gaps)
    - [Factor 2: Tooling Maturity](#factor-2-tooling-maturity)
- [Solution Implementation](#solution-implementation)
  - [Approach](#approach)
  - [Changes Made](#changes-made)
    - [Change 1: Test Fixtures (conftest.py)](#change-1-test-fixtures-conftestpy)
    - [Change 2: Test Functions](#change-2-test-functions)
    - [Change 3: Database Engine Configuration](#change-3-database-engine-configuration)
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

**Environment:** Test/CI

```python
MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.
Install greenlet
```

**Working Environments:** N/A - Issue occurred in all async test configurations

### Expected Behavior

Async tests should run successfully with pytest-asyncio, SQLAlchemy AsyncSession, and asyncpg driver, allowing proper testing of async database operations.

### Actual Behavior

Persistent `MissingGreenlet` errors when running any test that performs database operations through AsyncSession, despite implementing patterns from official documentation.

### Impact

- **Severity:** High
- **Affected Components:** pytest test suite, SQLAlchemy AsyncSession, asyncpg driver
- **User Impact:** Blocked ability to write async tests for database operations

## Investigation Steps

Document of five different approaches attempted, following official pytest-asyncio and SQLAlchemy documentation.

### Step 1: Session-Scoped Event Loop with Pooled Connections

**Hypothesis:** Using a session-scoped event loop with regular connection pooling would allow async database operations in tests.

**Investigation:**

Implemented session-scoped `event_loop` fixture with standard SQLAlchemy connection pool configuration.

```python
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

**Findings:**

Tests failed with `RuntimeError: attached to different loop` errors. asyncpg connections are bound to specific event loops and cannot be shared across different loop instances.

**Result:** ❌ Not the cause - asyncpg connections cannot be reused across event loops

### Step 2: NullPool with Session-Scoped Async Fixtures

**Hypothesis:** Using `NullPool` to prevent connection reuse would resolve event loop attachment errors.

**Investigation:**

Configured engine with `NullPool` to create new connections for each operation, preventing connection reuse across event loops.

```python
engine = create_async_engine(
    database_url,
    poolclass=NullPool
)
```

**Findings:**

Same event loop attachment errors persisted. Session-scoped async fixtures still created connections in different loop than tests.

**Result:** ❌ Not the cause - scope issue remained

### Step 3: NullPool with Manual Transaction Wrapping

**Hypothesis:** Manually wrapping sessions in transactions using `connection.begin()` would provide proper isolation.

**Investigation:**

Implemented manual transaction wrapping pattern from SQLAlchemy async documentation:

```python
async with engine.connect() as connection:
    async with connection.begin():
        session = AsyncSession(bind=connection)
        # test operations
```

**Findings:**

`MissingGreenlet` errors appeared when session bound to transaction-wrapped connection attempted database operations.

**Result:** ❌ Not the cause - greenlet context issues with transaction wrapping

### Step 4: Nested Transactions with Savepoints

**Hypothesis:** Using `begin_nested()` to allow commits as savepoints would enable proper test isolation.

**Investigation:**

Implemented nested transaction pattern with savepoint support:

```python
async with session.begin_nested():
    # test operations that call commit()
```

**Findings:**

`MissingGreenlet` errors occurred in event listener callbacks. Event listeners trying to create savepoints synchronously conflicted with async context.

**Result:** ❌ Not the cause - event system not fully async-aware

### Step 5: Clean Session Without Transaction Wrapping

**Hypothesis:** Simplifying to basic `AsyncSession(engine)` pattern would avoid transaction complexity issues.

**Investigation:**

Used minimal session pattern with rollback in finally block:

```python
session = AsyncSession(engine)
try:
    # test operations
finally:
    await session.rollback()
    await session.close()
```

**Findings:**

Even simple session creation hit greenlet issues with NullPool. Lazy-loaded relationships triggered queries that failed with `MissingGreenlet` errors.

**Result:** ❌ Not the cause - fundamental incompatibility with async testing patterns

## Root Cause Analysis

### Primary Cause

**Problem:** Incompatibility between asyncpg event loop binding, SQLAlchemy's greenlet bridge, and pytest-asyncio fixture management

The `MissingGreenlet` error occurs when SQLAlchemy tries to execute database operations but the greenlet context (required for async/await bridge) isn't properly set up. This happens because:

1. **asyncpg requires proper async context**: Every database operation must run in an async context
2. **NullPool creates connections on-demand**: Each query creates a new connection
3. **Lazy-loaded relationships trigger queries**: Accessing `connection.token` triggers a query
4. **Event listeners run synchronously**: SQLAlchemy event system isn't fully async-aware

**Why This Happens:**

The greenlet library provides a bridge between sync and async code in SQLAlchemy. When using AsyncSession with asyncpg, certain operations require the greenlet context to be properly initialized via `greenlet_spawn()`. However, pytest-asyncio's fixture management and asyncpg's event loop requirements create scenarios where this context is not properly established, especially when:

- Creating connections on-demand (NullPool)
- Accessing lazy-loaded relationships
- Handling transaction events
- Managing session lifecycle across test boundaries

**Impact:**

This caused complete inability to run async database tests, blocking development of proper test coverage for async database operations.

### Contributing Factors

#### Factor 1: Official Documentation Gaps

The official SQLAlchemy and pytest-asyncio documentation shows simple examples but doesn't address:

- How to handle code that calls `commit()` in services (not just `flush()`)
- How to handle lazy-loaded relationships in tests
- How NullPool interacts with asyncpg's event loop requirements
- The greenlet bridge complexities with pytest-asyncio fixture management

#### Factor 2: Tooling Maturity

pytest-asyncio + SQLAlchemy + asyncpg combination lacks mature real-world examples and battle-tested patterns for service layer testing with transactions.

## Solution Implementation

### Approach

After evaluating five potential solutions, the decision was made to adopt **synchronous testing pattern** following the FastAPI official template approach. This eliminates all async complexity in tests while maintaining full test coverage.

**Rationale:** FastAPI's official template uses synchronous TestClient for good reason - it properly handles transactions and database operations without async complexity. Application code remains async; only test code becomes synchronous.

### Changes Made

#### Change 1: Test Fixtures (conftest.py)

**Before:**

```python
@pytest.fixture(scope="session")
async def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def session():
    async with AsyncSession(engine) as session:
        yield session
```

**After:**

```python
@pytest.fixture
def session():
    with Session(sync_engine) as session:
        yield session
        session.rollback()
```

**Rationale:**

Synchronous Session fixture eliminates all greenlet and event loop complexity while providing proper test isolation with automatic rollback.

#### Change 2: Test Functions

**Before:**

```python
@pytest.mark.asyncio
async def test_create_provider(session):
    provider = Provider(name="test")
    session.add(provider)
    await session.commit()
    assert provider.id is not None
```

**After:**

```python
def test_create_provider(session):
    provider = Provider(name="test")
    session.add(provider)
    session.commit()
    assert provider.id is not None
```

**Rationale:**

Synchronous test functions work seamlessly with FastAPI TestClient and synchronous Session, matching official FastAPI testing patterns.

#### Change 3: Database Engine Configuration

**Before:**

```python
engine = create_async_engine(
    database_url,
    poolclass=NullPool
)
```

**After:**

```python
# Keep async engine for application
async_engine = create_async_engine(database_url)

# Add sync engine for tests
sync_engine = create_engine(test_database_url)
```

**Rationale:**

Separate engines allow application to remain async while tests use synchronous database operations.

### Implementation Steps

1. **Created synchronous test fixtures**

   ```bash
   # Updated conftest.py with sync Session patterns
   vim tests/conftest.py
   ```

2. **Converted test functions to synchronous**

   ```bash
   # Removed @pytest.mark.asyncio decorators
   # Changed async def to def
   # Removed await keywords
   find tests/ -name "test_*.py" -exec sed -i '' 's/@pytest.mark.asyncio//g' {} \;
   ```

3. **Updated TestClient usage**

   ```python
   # FastAPI TestClient handles async app with sync tests
   client = TestClient(app)
   response = client.post("/api/v1/providers")
   ```

4. **Verified all tests pass**

   ```bash
   make test
   # ✅ 39 tests passing, 51% coverage
   ```

## Verification

### Test Results

**Before Fix:**

```bash
MissingGreenlet errors on all async database tests
0 tests passing in async configuration
Complete test suite blocked
```

**After Fix:**

```bash
========== test session starts ==========
collected 39 items

tests/unit/ ......................... [  9 passed ]
tests/integration/ ................ [ 11 passed ]
tests/api/ ...................... [ 19 passed ]

========== 39 passed in 4.32s ==========
Coverage: 51%
Zero async/greenlet issues
```

### Verification Steps

1. **Test in test environment**

   ```bash
   make test-up
   make test
   ```

   **Result:** ✅ All 39 tests passing

2. **Test in CI environment**

   ```bash
   make ci-test
   ```

   **Result:** ✅ CI pipeline green, all tests passing

3. **Verify application still uses async**

   ```bash
   # Application endpoints remain async
   grep -r "async def" src/api/
   ```

   **Result:** ✅ Application code unchanged, still async

### Regression Testing

All existing test functionality maintained with synchronous approach. Verified:

- Database operations work correctly
- Transaction isolation between tests
- TestClient properly handles async FastAPI app
- Coverage metrics maintained

## Lessons Learned

### Technical Insights

1. **Async testing is genuinely complex**

   This isn't a skill issue, it's a tooling maturity issue. The combination of pytest-asyncio + SQLAlchemy + asyncpg lacks mature patterns for real-world service layer testing.

2. **pytest-asyncio + SQLAlchemy + asyncpg is a tough combo**

   Few real-world examples exist showing how to properly test service layers that perform commits and handle relationships.

3. **Official docs are incomplete**

   Documentation shows simple cases but doesn't address real service layer patterns with commits, relationships, and transaction management.

4. **Greenlet errors are cryptic**

   Hard to debug with multiple possible causes. Error messages don't clearly indicate the actual problem.

5. **Architecture matters for testing**

   Services that commit are harder to test than those that only flush. Testing concerns should influence architectural decisions.

### Process Improvements

1. **Follow framework official patterns**

   FastAPI template uses sync testing for good reasons. Should have consulted official template earlier.

2. **Don't fight the tools**

   If async testing is this complex, there's probably a better way. Pragmatism over theoretical purity.

3. **Consult official templates early**

   Would have saved 10+ hours of debugging to start with FastAPI's recommended testing approach.

4. **Document research thoroughly**

   Comprehensive documentation helps future decision-making and prevents repeating mistakes.

### Best Practices

- Use synchronous TestClient for FastAPI testing (official recommendation)
- Keep application code async, test code synchronous
- Follow proven patterns over theoretical purity
- Prioritize working tests over async testing ideology
- Separate test and application database engine configurations
- Use FastAPI TestClient's built-in transaction handling

## Future Improvements

### Short-Term Actions

1. **Expand test coverage to 85%+**

   **Timeline:** Next development phase

   **Owner:** Development team

2. **Document testing patterns comprehensively**

   **Timeline:** Complete

   **Owner:** Done - see development/guides/testing-guide.md

### Long-Term Improvements

1. **Monitor pytest-asyncio maturity**

   Revisit async testing when tooling matures and real-world examples are available. Track pytest-asyncio and SQLAlchemy async testing evolution.

2. **Contribute findings to community**

   Document this journey to help others avoid same issues. Consider blog post or documentation contribution to pytest-asyncio or SQLAlchemy.

### Monitoring & Prevention

N/A - Issue resolved by architectural decision to use synchronous testing pattern. Future projects should start with FastAPI official testing patterns rather than attempting async testing patterns.

## References

**Related Documentation:**

- [Testing Strategy](../../testing/strategy.md) - Complete testing approach
- [Testing Guide](../../development/guides/testing-guide.md) - Practical testing patterns
- [Testing Best Practices](../guides/testing-best-practices.md) - Testing patterns and conventions

**External Resources:**

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/) - Official sync testing pattern
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Async ORM docs
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/) - Async testing plugin

**Related Issues:**

- Phase 3 Testing Migration - Complete rewrite to synchronous pattern
- Testing Infrastructure Fix - Fixture management improvements

---

## Document Information

**Template:** [troubleshooting-template.md](../../templates/troubleshooting-template.md)
**Created:** 2025-10-02
**Last Updated:** 2025-10-20
