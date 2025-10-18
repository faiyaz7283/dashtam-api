# Async Testing Greenlet Errors - Troubleshooting Guide

**Date:** 2025-10-02
**Issue:** MissingGreenlet errors when running async tests with pytest-asyncio + SQLAlchemy + asyncpg
**Resolution:** Adopted synchronous testing pattern with FastAPI TestClient
**Status:** ✅ RESOLVED

---

## Executive Summary

The Dashtam project encountered persistent `MissingGreenlet` errors when implementing async testing patterns with pytest-asyncio 1.2.0, SQLAlchemy 2.0.43, and asyncpg. Despite following official documentation and implementing five different approaches (session-scoped event loops, NullPool configurations, transaction wrapping, savepoints, and clean sessions), all attempts resulted in greenlet context errors.

After extensive investigation, the root cause was identified as incompatibilities between asyncpg's event loop requirements, SQLAlchemy's greenlet bridge, and pytest-asyncio's fixture management. The solution was to adopt the synchronous testing pattern recommended by the FastAPI official template, using TestClient with synchronous Session objects. This eliminated all async complexity while maintaining full test coverage.

**Key Decision**: Synchronous testing (def test_*, not async def) with FastAPI TestClient (matches FastAPI official pattern)

---

## Table of Contents

1. [Initial Problem](#initial-problem)
2. [Investigation Steps](#investigation-steps)
   - [Step 1: Session-Scoped Event Loop](#step-1-session-scoped-event-loop-with-pooled-connections)
   - [Step 2: NullPool with Async Fixtures](#step-2-nullpool-with-session-scoped-async-fixtures)
   - [Step 3: Manual Transaction Wrapping](#step-3-nullpool-with-manual-transaction-wrapping)
   - [Step 4: Nested Transactions](#step-4-nested-transactions-with-savepoints)
   - [Step 5: Clean Session Pattern](#step-5-clean-session-without-transaction-wrapping)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Solution Implementation](#solution-implementation)
5. [Verification](#verification)
6. [Lessons Learned](#lessons-learned)
7. [Future Improvements](#future-improvements)
8. [References](#references)

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

---

## Investigation Steps

Document of five different approaches attempted, following official pytest-asyncio and SQLAlchemy documentation.

### Step 1: Session-Scoped Event Loop with Pooled Connections

**Approach**: Session-scoped `event_loop` fixture with regular connection pooling
**Result**: `RuntimeError: attached to different loop` errors
**Why**: asyncpg connections are bound to specific event loops and can't be shared

### Step 2: NullPool with Session-Scoped Async Fixtures

**Approach**: Used `NullPool` to prevent connection reuse, async session-scoped setup
**Result**: Same event loop attachment errors
**Why**: Session-scoped async fixtures still created connections in different loop than tests

### Step 3: NullPool with Manual Transaction Wrapping

**Approach**: Wrap session in manual transaction using `connection.begin()`
**Result**: `MissingGreenlet` errors
**Why**: Session bound to transaction-wrapped connection has greenlet context issues

### Step 4: Nested Transactions with Savepoints

**Approach**: Use `begin_nested()` to allow commits as savepoints
**Result**: `MissingGreenlet` errors in event listener callbacks
**Why**: Event listeners trying to create savepoints synchronously

### Step 5: Clean Session Without Transaction Wrapping

**Approach**: Simple `AsyncSession(engine)` with rollback in finally block
**Result**: `MissingGreenlet` errors
**Why**: Even simple session creation hits greenlet issues with NullPool

---

## Root Cause Analysis

### Primary Cause

**Problem:** Incompatibility between asyncpg event loop binding, SQLAlchemy's greenlet bridge, and pytest-asyncio fixture management

The `MissingGreenlet` error occurs when SQLAlchemy tries to execute database operations but the greenlet context (required for async/await bridge) isn't properly set up. This happens because:

1. **asyncpg requires proper async context**: Every database operation must run in an async context
2. **NullPool creates connections on-demand**: Each query creates a new connection
3. **Lazy-loaded relationships trigger queries**: Accessing `connection.token` triggers a query
4. **Event listeners run synchronously**: SQLAlchemy event system isn't fully async-aware

### Contributing Factors

#### Factor 1: Official Documentation Gaps

The official docs show simple examples but don't address:

- How to handle code that calls `commit()` in services (not just `flush()`)
- How to handle lazy-loaded relationships in tests
- How NullPool interacts with asyncpg's event loop requirements
- The greenlet bridge complexities with pytest-asyncio

---

## Solution Implementation

### Approach

After evaluating five potential solutions, the decision was made to adopt **Option B: Synchronous Testing Pattern** following the FastAPI official template approach.

### Potential Solutions Evaluated

#### Option A: Use psycopg (not asyncpg)

**Pros**: psycopg3 has better sync/async bridge, fewer greenlet issues
**Cons**: Requires changing DATABASE_URL driver, testing migration
**Effort**: Medium (2-3 hours)

#### Option B: Use Sync SQLAlchemy for Tests Only

**Pros**: Eliminates all async complexity in tests
**Cons**: Tests don't match production code paths, requires dual fixtures
**Effort**: Medium (3-4 hours)

#### Option C: Mock Database Layer in Unit Tests

**Pros**: Fast tests, no database complexity
**Cons**: Not testing actual database interactions, requires extensive mocking
**Effort**: High (rewrite existing tests)

#### Option D: Use pytest-postgresql with Factory Pattern

**Pros**: Proven pattern for PostgreSQL testing
**Cons**: Additional dependency, different from production setup
**Effort**: Medium-High (4-5 hours)

#### Option E: Simplify Service Layer (Remove Commits from Services)

**Pros**: Services become testable with simple flush() operations
**Cons**: Architectural change, commits move to API layer
**Effort**: Medium (refactor services, update tests)

### Selected Solution: Synchronous Testing Pattern

Based on research, time investment, and FastAPI best practices, **Option B (Sync SQLAlchemy for Tests)** was selected:

#### Phase 1: Refactor Service Layer (2-3 hours)

1. Remove `await session.commit()` from service methods
2. Services only use `flush()` to persist within transaction
3. API endpoints handle transaction commits
4. This matches common best practices (services shouldn't commit)

#### Phase 2: Update Test Fixtures (1 hour)

1. Simple `AsyncSession(engine)` pattern works when services only flush
2. Tests can verify data with `flush()` + `refresh()`
3. No complex transaction wrapping needed

#### Phase 3: Add Integration Tests (2-3 hours)

1. Separate integration tests that test full API → Service → DB flow
2. These tests use FastAPI's TestClient (handles transactions properly)
3. Cover the commit scenarios end-to-end

**Total Effort**: 5-7 hours

**Benefits**:

- Cleaner architecture (separation of concerns)
- Easier to test
- Matches industry best practices
- No async/greenlet complexity in unit tests

### Implementation Steps

1. **Adopted FastAPI TestClient pattern** (synchronous)
2. **Created synchronous Session fixtures** for test database
3. **Rewrote test functions** as `def test_*()` instead of `async def`
4. **Updated conftest.py** with synchronous patterns
5. **Verified all tests pass** with new approach

---

## Verification

### Test Results

**Before Fix:**

```bash
MissingGreenlet errors on all async database tests
0 tests passing in async configuration
```

**After Fix:**

```bash
39 tests passing (9 unit, 11 integration, 19 API)
51% code coverage
Zero async/greenlet issues
```

### Verification Steps

1. **Converted all tests to synchronous pattern**

   **Result:** ✅ All tests passing

2. **Ran full test suite in CI/CD**

   **Result:** ✅ CI pipeline green

### Regression Testing

All existing test functionality maintained with synchronous approach. Application code remains async; only test code is synchronous.

---

## Lessons Learned

### Technical Insights

1. **Async testing is genuinely complex**: This isn't a skill issue, it's a tooling maturity issue
2. **pytest-asyncio + SQLAlchemy + asyncpg is a tough combo**: Few real-world examples exist
3. **Official docs are incomplete**: They show simple cases, not real service layer patterns
4. **Greenlet errors are cryptic**: Hard to debug, multiple possible causes
5. **Architecture matters**: Services that commit are harder to test than those that don't

### Process Improvements

1. **Follow framework official patterns**: FastAPI template uses sync testing for good reasons
2. **Don't fight the tools**: If async testing is this complex, there's probably a better way
3. **Consult official templates early**: Would have saved 10+ hours of debugging
4. **Document research thoroughly**: Helps future decision-making

### Best Practices

- Use synchronous TestClient for FastAPI testing (official recommendation)
- Keep application code async, test code synchronous
- Follow proven patterns over theoretical purity
- Prioritize working tests over async testing ideology

### Alternative Path Not Taken

Given the time invested, another valid option was:

1. Mark tests as `@pytest.mark.skip("Async testing infrastructure WIP")`
2. Focus on feature development
3. Revisit testing infrastructure when more examples/docs available
4. Use manual testing + integration environment for now

---

## Future Improvements

### Short-Term Actions

1. **Expand test coverage to 85%+**

   **Timeline:** Next 2 sprints

   **Owner:** Development team

2. **Document testing patterns**

   **Timeline:** Complete

   **Owner:** Done - see testing/guide.md

### Long-Term Improvements

1. **Monitor pytest-asyncio maturity**

   Revisit async testing when tooling matures and real-world examples are available

2. **Contribute findings to community**

   Document this journey to help others avoid same issues

### Monitoring & Prevention

N/A - Issue resolved by architectural decision to use synchronous testing

---

## References

**Related Documentation:**

- [Testing Strategy](../testing/strategy.md) - Complete testing approach
- [Testing Guide](../testing/guide.md) - Practical testing patterns
- [Testing Best Practices](../testing/best-practices.md) - Standards and patterns

**External Resources:**

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/) - Official sync testing pattern
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Async ORM docs
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/) - Async testing plugin

**Related Issues:**

- Phase 3 Testing Migration - Complete rewrite to synchronous pattern
- Testing Infrastructure Fix - Fixture management improvements

---

## Document Information

**Category:** Troubleshooting
**Created:** 2025-10-02
**Last Updated:** 2025-10-17
**Status:** ✅ RESOLVED (Synchronous testing pattern adopted)
**Environment:** Test/CI
**Components Affected:** pytest, SQLAlchemy AsyncSession, asyncpg, test fixtures
**Resolution:** Adopted FastAPI official synchronous testing pattern with TestClient
**Related Docs:** [Testing Strategy](../testing/strategy.md), [Testing Guide](../testing/guide.md)
