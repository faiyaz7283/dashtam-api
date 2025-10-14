# Async Testing Research & Implementation Summary

## Current Status

We've spent significant effort implementing proper async testing patterns for the Dashtam project, following official documentation for:
- pytest-asyncio 1.2.0
- SQLAlchemy 2.0.43  
- asyncpg (via SQLAlchemy async driver)

**Current Issue**: Persistent `MissingGreenlet` errors when running tests despite implementing multiple approaches from official documentation.

## What We've Tried (In Order)

### 1. Session-Scoped Event Loop with Pooled Connections
**Approach**: Session-scoped `event_loop` fixture with regular connection pooling
**Result**: `RuntimeError: attached to different loop` errors
**Why**: asyncpg connections are bound to specific event loops and can't be shared

### 2. NullPool with Session-Scoped Async Fixtures  
**Approach**: Used `NullPool` to prevent connection reuse, async session-scoped setup
**Result**: Same event loop attachment errors
**Why**: Session-scoped async fixtures still created connections in different loop than tests

### 3. NullPool with Manual Transaction Wrapping
**Approach**: Wrap session in manual transaction using `connection.begin()`
**Result**: `MissingGreenlet` errors
**Why**: Session bound to transaction-wrapped connection has greenlet context issues

### 4. Nested Transactions with Savepoints
**Approach**: Use `begin_nested()` to allow commits as savepoints
**Result**: `MissingGreenlet` errors in event listener callbacks
**Why**: Event listeners trying to create savepoints synchronously

### 5. Clean Session Without Transaction Wrapping  
**Approach**: Simple `AsyncSession(engine)` with rollback in finally block
**Result**: `MissingGreenlet` errors
**Why**: Even simple session creation hits greenlet issues with NullPool

## The Core Problem

The `MissingGreenlet` error occurs when SQLAlchemy tries to execute database operations but the greenlet context (required for async/await bridge) isn't properly set up. This happens because:

1. **asyncpg requires proper async context**: Every database operation must run in an async context
2. **NullPool creates connections on-demand**: Each query creates a new connection
3. **Lazy-loaded relationships trigger queries**: Accessing `connection.token` triggers a query
4. **Event listeners run synchronously**: SQLAlchemy event system isn't fully async-aware

## Official Documentation Gaps

The official docs show simple examples but don't address:
- How to handle code that calls `commit()` in services (not just `flush()`)
- How to handle lazy-loaded relationships in tests
- How NullPool interacts with asyncpg's event loop requirements
- The greenlet bridge complexities with pytest-asyncio

## Potential Solutions (Not Yet Tried)

### Option A: Use psycopg (not asyncpg)
**Pros**: psycopg3 has better sync/async bridge, fewer greenlet issues
**Cons**: Requires changing DATABASE_URL driver, testing migration
**Effort**: Medium (2-3 hours)

### Option B: Use Sync SQLAlchemy for Tests Only
**Pros**: Eliminates all async complexity in tests
**Cons**: Tests don't match production code paths, requires dual fixtures
**Effort**: Medium (3-4 hours)

### Option C: Mock Database Layer in Unit Tests
**Pros**: Fast tests, no database complexity
**Cons**: Not testing actual database interactions, requires extensive mocking
**Effort**: High (rewrite existing tests)

### Option D: Use pytest-postgresql with Factory Pattern
**Pros**: Proven pattern for PostgreSQL testing
**Cons**: Additional dependency, different from production setup
**Effort**: Medium-High (4-5 hours)

### Option E: Simplify Service Layer (Remove Commits from Services)
**Pros**: Services become testable with simple flush() operations
**Cons**: Architectural change, commits move to API layer
**Effort**: Medium (refactor services, update tests)

## Recommended Path Forward

Based on research and time investment, I recommend **Option E + Targeted Integration Tests**:

### Phase 1: Refactor Service Layer (2-3 hours)
1. Remove `await session.commit()` from service methods
2. Services only use `flush()` to persist within transaction
3. API endpoints handle transaction commits
4. This matches common best practices (services shouldn't commit)

### Phase 2: Update Test Fixtures (1 hour)
1. Simple `AsyncSession(engine)` pattern works when services only flush
2. Tests can verify data with `flush()` + `refresh()`
3. No complex transaction wrapping needed

### Phase 3: Add Integration Tests (2-3 hours)
1. Separate integration tests that test full API → Service → DB flow
2. These tests use FastAPI's TestClient (handles transactions properly)
3. Cover the commit scenarios end-to-end

**Total Effort**: 5-7 hours
**Benefits**: 
- Cleaner architecture (separation of concerns)
- Easier to test
- Matches industry best practices
- No async/greenlet complexity in unit tests

## Alternative: Pause Tests, Ship Features

Given the time invested, another valid option is:
1. Mark tests as `@pytest.mark.skip("Async testing infrastructure WIP")`
2. Focus on feature development
3. Revisit testing infrastructure when more examples/docs available
4. Use manual testing + integration environment for now

## Files Changed

- `tests/conftest.py`: Completely rewritten with best practices patterns
- `pytest.ini`: Added with proper async configuration
- `tests/conftest_old.py`: Backup of original (for reference)
- `PHASE_3_PROGRESS.md`: Tracking document
- `PHASE_3_HANDOFF.md`: Status at pause point

## Key Learnings

1. **Async testing is genuinely complex**: This isn't a skill issue, it's a tooling maturity issue
2. **pytest-asyncio + SQLAlchemy + asyncpg is a tough combo**: Few real-world examples exist
3. **Official docs are incomplete**: They show simple cases, not real service layer patterns
4. **Greenlet errors are cryptic**: Hard to debug, multiple possible causes
5. **Architecture matters**: Services that commit are harder to test than those that don't

## Resources Consulted

- SQLAlchemy 2.0 Async Documentation
- pytest-asyncio Official Docs  
- asyncpg GitHub Issues
- Stack Overflow threads on greenlet errors
- FastAPI testing patterns
- Real-world project examples (FastAPI + SQLAlchemy + pytest)

## Conclusion

We've implemented the patterns exactly as documented, but hit edge cases that official docs don't cover. The path forward requires either:
1. Architectural changes (recommended)
2. Different tooling choices
3. Accepting test limitations for now

All approaches are valid - the choice depends on project priorities and timeline.
