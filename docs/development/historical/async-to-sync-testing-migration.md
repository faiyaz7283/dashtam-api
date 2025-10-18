# Async-to-Sync Testing Migration - Historical Record

Historical documentation of the migration from async testing patterns to synchronous testing with FastAPI TestClient (September 2025).

---

## Status

**Migration Status:** ✅ **COMPLETE** (as of September 2025)

**Current Testing Approach:** Synchronous testing with FastAPI TestClient - See [Testing Strategy](../testing/strategy.md)

**Architectural Decision:** See [Async Testing Decision](../architecture/async-testing-decision.md)

---

## Purpose

This document preserves the implementation plan and migration steps that were used to transition Dashtam's test suite from async testing (with pytest-asyncio) to synchronous testing (with FastAPI TestClient).

**Why preserve this?**

- Historical reference for understanding the evolution of our testing approach
- Lessons learned that may benefit similar projects
- Documentation of technical debt that was resolved
- Context for future architectural decisions

---

## Migration Overview

**Problem:** Async testing with pytest-asyncio caused greenlet errors, event loop conflicts, and test flakiness.

**Solution:** Migrated to synchronous testing using FastAPI's official pattern (TestClient with sync Session).

**Duration:** Approximately 1 week (September 2025)

**Outcome:**

- ✅ Zero async/greenlet issues
- ✅ Reliable test suite (295+ tests passing)
- ✅ Simpler test code (no async/await)
- ✅ Faster test execution

---

## Implementation Plan (Historical)

This was the original phased migration plan. All phases are now complete.

### Phase 1: Core Test Infrastructure

**Goal:** Implement new synchronous test fixtures and configuration

**Tasks:**

1. **Create new `tests/conftest.py`** with synchronous patterns

```python
from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, create_engine
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.core.db import init_db
from src.main import app
from src.models import User, Provider, ProviderConnection, ProviderToken

# Use in-memory SQLite for fast tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    """Session-scoped database fixture."""
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        init_db(session)
        yield session
        # Cleanup
        session.exec(delete(ProviderToken))
        session.exec(delete(ProviderConnection))
        session.exec(delete(Provider))
        session.exec(delete(User))
        session.commit()
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(db: Session) -> Generator[Session, None, None]:
    """Function-scoped session for test isolation."""
    yield db

@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Test client for API requests."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    """Headers with superuser authentication."""
    return get_superuser_token_headers(client)
```

**Key Patterns:**

- Session-scoped engine for performance
- Function-scoped session for isolation
- Module-scoped TestClient for reuse
- No async fixtures

**Status:** ✅ Complete

### Phase 2: Refactor Service Layer

**Goal:** Remove commit calls from services, move to API layer

**Problem:** Services calling `await session.commit()` caused issues in test transactions.

**Solution:** Use `flush()` in services, `commit()` in API layer.

**Before (Problematic):**

```python
# src/services/token_service.py
async def store_initial_tokens(self, ...):
    # ... business logic ...
    self.session.add(token)
    await self.session.commit()  # ❌ Problematic in tests
    return token
```

**After (Clean):**

```python
# src/services/token_service.py
async def store_initial_tokens(self, ...):
    # ... business logic ...
    self.session.add(token)
    await self.session.flush()  # ✅ Persist in transaction
    await self.session.refresh(token)  # Load relationships
    return token

# src/api/endpoints/providers.py
@router.post("/providers/tokens")
async def store_tokens(...):
    token = await token_service.store_initial_tokens(...)
    await session.commit()  # ✅ Commit at API boundary
    return token
```

**Benefits:**

- Services are testable with simple flush()
- API layer controls transactions
- Follows separation of concerns
- Matches industry best practices

**Status:** ✅ Complete

### Phase 3: Migrate Tests

**Goal:** Convert all tests from async to sync patterns

**Directory Structure Created:**

```text
tests/
├── __init__.py
├── conftest.py                 # Global fixtures
├── pytest.ini                  # Pytest configuration
├── unit/                       # Unit tests (no DB)
│   ├── services/
│   │   ├── test_encryption_service.py
│   │   └── test_token_validation.py
│   └── utils/
│       └── test_helpers.py
├── integration/                # Integration tests (with DB)
│   ├── conftest.py
│   ├── crud/
│   │   ├── test_user_crud.py
│   │   ├── test_provider_crud.py
│   │   └── test_token_crud.py
│   └── services/
│       ├── test_token_service.py
│       └── test_provider_service.py
└── api/                       # API/E2E tests
    ├── conftest.py
    └── routes/
        ├── test_auth.py
        ├── test_providers.py
        └── test_health.py
```

**Migration Steps:**

1. **Unit Tests** (easiest first)
   - Remove `@pytest.mark.asyncio`
   - Change `async def` to `def`
   - Change `await` calls to sync calls

2. **Integration Tests**
   - Use `db: Session` fixture
   - Remove async session operations
   - Keep database operations

3. **API Tests**
   - Use `TestClient` sync API
   - No async/await needed

**Example Migration:**

Before:

```python
@pytest.mark.asyncio
async def test_create_provider(db: AsyncSession):
    provider = await crud.create_provider(session=db, ...)
    assert provider.id is not None
```

After:

```python
def test_create_provider(db: Session):
    provider = crud.create_provider(session=db, ...)
    assert provider.id is not None
```

**Status:** ✅ Complete

### Phase 4: Verification and Cleanup

**Goal:** Ensure all tests pass and remove old async code

**Tasks:**

1. **Run all tests:**

   ```bash
   pytest tests/ -v
   ```

2. **Verify coverage:**

   ```bash
   pytest --cov=src --cov-report=html
   ```

3. **Backup old async code:**

   ```bash
   mv tests/conftest.py tests/conftest_async_old.py
   mv tests/unit tests/unit_old_async
   ```

4. **Remove pytest-asyncio dependency** (if no longer needed)

**Status:** ✅ Complete

---

## Migration Path (Step-by-Step)

This was the detailed migration procedure followed:

### Step 1: Backup Current Tests

```bash
mv tests/conftest.py tests/conftest_old_async.py
mv tests/unit tests/unit_old_async
```

### Step 2: Implement New conftest.py

- Use sync Session pattern from FastAPI template
- Remove all async fixtures
- Use TestClient instead of AsyncClient

### Step 3: Migrate Tests One Category at a Time

**Order:**

1. Unit tests (fastest, no dependencies)
2. Integration tests (database operations)
3. API tests (complete workflows)

### Step 4: Run and Verify

```bash
# Run unit tests (fast)
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run API tests
pytest tests/api -v

# Run all with coverage
pytest --cov=src --cov-report=html
```

---

## PDF Guide Patterns (Not Used)

During research, we reviewed async testing patterns from "A Comprehensive Guide to Testing FastAPI and SQLAlchemy 2.0 with pytest-asyncio". These patterns were documented but **not implemented** as we chose the synchronous approach.

### Pattern: Function-Scoped Engine with NullPool

```python
@pytest.fixture(scope="function")
def test_engine(test_settings):
    engine = create_async_engine(
        test_settings.test_database_url,
        poolclass=NullPool,  # Critical for async testing
    )
    yield engine
    asyncio.run(engine.dispose())
```

**Why not used:** Unnecessary with synchronous testing.

### Pattern: Transactional Isolation with Savepoints

```python
@pytest_asyncio.fixture
async def db_session(test_engine):
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint"  # KEY PATTERN
        )
        yield session
        await session.close()
        await connection.rollback()
```

**Why not used:** TestClient with sync Session handles isolation automatically.

### Key Takeaways from PDF Guide (For Reference)

If async testing is ever needed:

1. **Never create session-scoped event loops** - Causes "attached to different loop" errors
2. **Use `NullPool` for async engines** - Prevents connection reuse across loops
3. **Use `join_transaction_mode="create_savepoint"`** - For transactional isolation
4. **Avoid `pytest-xdist` with session-scoped async fixtures** - Creates conflicts
5. **Let pytest-asyncio manage loops** - Don't create custom event_loop fixtures

---

## Lessons Learned

### What Worked Well

1. **Phased approach:** Migrating category by category reduced risk
2. **Backup strategy:** Keeping old async code allowed comparison
3. **FastAPI pattern:** Following official template avoided common pitfalls
4. **Service refactoring:** Moving commits to API layer improved testability
5. **Documentation:** Recording decisions helped team understanding

### Challenges Encountered

1. **Initial resistance:** Team concern about not testing "real" async code
2. **Service layer changes:** Required coordination across multiple services
3. **Test data setup:** Needed rethinking of fixture scopes
4. **Coverage gaps:** Some tests needed rewriting, not just conversion

### Mistakes to Avoid

1. **Don't try async testing first** - Start with synchronous if using FastAPI
2. **Don't mix approaches** - Consistency matters more than theoretical purity
3. **Don't skip service refactoring** - Commits in services cause test issues
4. **Don't ignore official patterns** - FastAPI team knows their framework best

---

## Comparison: Before vs After

### Test Complexity

**Before (Async):**

```python
@pytest.mark.asyncio
async def test_create_user(db: AsyncSession):
    user = User(email="test@example.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert user.id is not None
```

**After (Sync):**

```python
def test_create_user(db: Session):
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
```

### Fixture Complexity

**Before (Async):**

```python
@pytest_asyncio.fixture
async def db(test_engine):
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        await session.close()
        await connection.rollback()
```

**After (Sync):**

```python
@pytest.fixture(scope="session")
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

### Test Reliability

**Before:** Occasional failures due to event loop issues, timing problems

**After:** 100% reliable - 295+ tests passing consistently

### Developer Experience

**Before:**

- Difficult to write tests
- Confusing error messages
- Slow feedback loop

**After:**

- Easy to write tests
- Clear error messages
- Fast feedback loop

---

## Current State (2025-10-18)

**Testing Infrastructure:**

- ✅ Synchronous testing fully implemented
- ✅ 295+ tests passing
- ✅ 76% code coverage (target: 85%)
- ✅ Zero async/greenlet issues
- ✅ FastAPI TestClient with synchronous SQLModel Session
- ✅ Docker-based test environment with isolated PostgreSQL
- ✅ GitHub Actions CI/CD with automated testing
- ✅ Codecov integration for coverage tracking

**Test Suite Performance:**

- Unit tests: < 100ms each
- Integration tests: < 500ms each
- API tests: < 1s each
- Full suite: < 30s total

**Next Steps:**

- Expand test coverage to 85%+
- Add more integration tests for provider operations
- Improve API test coverage for edge cases

---

## References

- [Async Testing Decision](../architecture/async-testing-decision.md) - ADR for this migration
- [Testing Strategy](../testing/strategy.md) - Current testing approach
- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI Official Template](https://github.com/fastapi/full-stack-fastapi-template)
- [Pytest Documentation](https://docs.pytest.org/)

---

**Note:** This document is historical reference only. For current testing practices, see [Testing Strategy](../testing/strategy.md).
