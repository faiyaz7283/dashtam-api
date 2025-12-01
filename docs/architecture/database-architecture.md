# Database Architecture

## Overview

The database layer in Dashtam follows hexagonal architecture principles where
the database is purely an infrastructure concern. The domain layer defines what
it needs through protocols, and the infrastructure layer provides concrete
implementations.

**Purpose**: Comprehensive architecture guide for database setup following
hexagonal architecture, SOLID principles, and clean slate patterns.

---

## Key Architecture Principles

### 1. Hexagonal Architecture Compliance

**Domain defines the PORT (what it needs)**:

```python
# src/domain/protocols/repositories.py
from typing import Protocol

class BaseRepository(Protocol):
    """Repository protocol - domain defines what it needs."""
    
    async def save(self, entity: Any) -> None:
        """Save an entity."""
        ...
    
    async def delete(self, entity: Any) -> None:
        """Delete an entity."""
        ...
```

**Infrastructure provides the ADAPTER (implementation)**:

```python
# src/infrastructure/persistence/base_repository.py
from sqlalchemy.ext.asyncio import AsyncSession

class SQLAlchemyRepository:
    """Concrete implementation - infrastructure provides the how."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, entity: Any) -> None:
        # Actual database operations
        ...
```

### 2. Dependency Injection Pattern

**No direct instantiation** - Dependencies are injected:

```python
# ✅ CORRECT - Dependency Injection
class UserService:
    def __init__(self, repository: BaseRepository):
        self.repository = repository  # Injected, not created
    
    async def create_user(self, data: dict) -> User:
        user = User(**data)
        await self.repository.save(user)
        return user

# ❌ WRONG - Direct coupling
class UserService:
    def __init__(self):
        # Creating dependency = tight coupling!
        self.repository = SQLAlchemyRepository(get_session())
```

### 3. SOLID Principles

**Single Responsibility**:

- `database.py` - Only manages database connections and sessions
- `base.py` - Only defines base model structure
- Repository classes - Only handle data persistence for one entity type

**Open/Closed**:

- Base classes are open for extension, closed for modification
- New features extend base classes, don't modify them

**Liskov Substitution**:

- Any repository implementation can replace another
- Test repositories can replace production repositories

**Interface Segregation**:

- Small, focused protocols (not one giant repository interface)
- Entities only depend on protocols they actually use

**Dependency Inversion**:

- High-level modules (domain) don't depend on low-level modules (database)
- Both depend on abstractions (protocols)

## File Structure

**Current Implementation**:

```text
src/
├── core/
│   ├── config.py                    # Settings with database URL
│   └── result.py                     # Result types for error handling
├── domain/
│   └── protocols/
│       └── repositories.py          # Repository protocols (ports)
├── infrastructure/
│   ├── errors.py                    # Infrastructure-specific error types
│   └── persistence/
│       ├── __init__.py
│       ├── base.py                  # BaseModel with UUID/timestamps
│       └── database.py              # Database connection manager

tests/
├── integration/
│   └── test_infrastructure_persistence_database.py  # Database integration tests
└── unit/
    └── (future domain and application tests)

alembic/
├── env.py                           # Alembic async configuration
├── script.py.mako                   # Migration template  
└── versions/                        # Migration files
```

**Note**: This is the foundation. Repositories, models, and domain entities
will be added in future phases.

## Integration with Other Architecture Components

### Domain Events Integration

**Critical Database Operations Emit Events** (from `/tmp/domain-events-architecture.md`):

The database layer participates in domain events for critical operations:

```python
# When a critical database operation occurs, emit event
from src.domain.events import UserPasswordChanged

# In application layer (NOT in repository)
class ChangePasswordHandler:
    async def handle(self, cmd: ChangePassword) -> Result[None, Error]:
        # Update in database
        user.password_hash = hash_password(cmd.new_password)
        await self.user_repo.save(user)
        
        # Emit domain event (triggers audit, logging, notifications)
        await self.event_bus.publish(UserPasswordChanged(
            event_id=uuid7(),
            occurred_at=datetime.now(UTC),
            user_id=user.id,
        ))
```

**Database operations that trigger events**:

- User registration → `UserRegistered`
- Password changes → `UserPasswordChanged`
- Provider connections → `ProviderConnected`
- Account deletions → `AccountDeleted`

### Audit Trail Integration

**All Critical Database Operations Are Audited** (from `/tmp/audit-trail-architecture.md`):

```python
# Audit service records WHO did WHAT, WHEN, WHERE
from src.domain.protocols.audit import AuditProtocol, AuditAction

class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        audit: AuditProtocol,  # Injected audit service
    ):
        self.user_repo = user_repo
        self.audit = audit
    
    async def delete_user(self, user_id: UUID, admin_id: UUID) -> Result[None, Error]:
        # Perform database operation
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            return Failure(NotFoundError())
        
        await self.user_repo.delete(user)
        
        # Record in audit trail (immutable, 7+ year retention)
        await self.audit.record(
            user_id=admin_id,
            action=AuditAction.ADMIN_USER_DELETED,
            resource_type=ResourceType.USER,
            resource_id=user_id,
            result=AuditResult.SUCCESS,
            metadata={"deleted_email": user.email},
        )
```

**Database operations requiring audit**:

- All write operations (CREATE, UPDATE, DELETE)
- Sensitive read operations (viewing financial data)
- Failed authentication attempts
- Admin operations

### Error Handling Integration

**Result Types Throughout** (from `/tmp/error-handling-architecture.md`):

Database operations return Result types, NOT exceptions:

```python
from src.core.result import Result, Success, Failure
from src.core.errors import NotFoundError
from src.infrastructure.errors import DatabaseError

class UserRepository:
    async def find_by_id(self, user_id: UUID) -> Result[User, NotFoundError]:
        try:
            model = await self.session.get(UserModel, user_id)
            if not model:
                return Failure(NotFoundError(f"User {user_id} not found"))
            return Success(model.to_entity())
        except SQLAlchemyError as e:
            # Log technical error
            logger.error("Database query failed", error=e)
            # Return domain error
            return Failure(DatabaseError("Failed to fetch user"))
```

**Error mapping layers**:

- Infrastructure: Database exceptions → Domain errors
- Application: Domain errors → Application errors
- Presentation: Application errors → RFC 7807 Problem Details

### Structured Logging Integration

**All Database Operations Are Logged** (from `/tmp/structured-logging-architecture.md`):

```python
from src.domain.protocols.logger import LoggerProtocol

class Database:
    def __init__(self, database_url: str, logger: LoggerProtocol):
        self.logger = logger
        self.engine = create_async_engine(database_url)
        
        # Log connection established
        self.logger.info(
            "Database connection established",
            database_url=database_url.split('@')[1],  # Hide credentials
            pool_size=20,
        )
    
    @asynccontextmanager
    async def get_session(self):
        trace_id = get_current_trace_id()
        
        self.logger.debug(
            "Creating database session",
            trace_id=trace_id,
        )
        
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
                self.logger.debug(
                    "Database transaction committed",
                    trace_id=trace_id,
                )
            except Exception as e:
                await session.rollback()
                self.logger.error(
                    "Database transaction rolled back",
                    error=e,
                    trace_id=trace_id,
                )
                raise
```

## Core Layer Integration

**Important**: The database layer uses utilities from `src/core/` and domain/infrastructure:

- **Result Types** (`src/core/result.py`): For explicit error handling
- **Core Error Classes** (`src/core/errors/`): Base error types (DomainError,
  ValidationError, NotFoundError, etc.)
- **Infrastructure Errors** (`src/infrastructure/errors/`): DatabaseError,
  CacheError, etc.
- **Validation** (`src/core/validation.py`): Common validation functions

All domain operations should return Result types instead of raising exceptions:

```python
from src.core.result import Result, Success, Failure
from src.core.errors import ValidationError, NotFoundError

async def find_user(self, user_id: UUID) -> Result[User, NotFoundError]:
    """Find user by ID, returning Result type."""
    model = await self.session.get(UserModel, user_id)
    if not model:
        return Failure(NotFoundError(f"User {user_id} not found"))
    return Success(model.to_entity())
```

## Architecture Layers

### Domain Layer (Pure Business Logic)

**Location**: `src/domain/`

**Responsibilities**:

- Define repository protocols (what operations are needed)
- Define entities (what data looks like)
- Define value objects (immutable values)
- Define domain events (things that happened)
- ZERO knowledge of database implementation

**Example**:

```python
# src/domain/entities/base.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from src.core.result import Result, Success, Failure
from src.core.errors import ValidationError

@dataclass(slots=True, kw_only=True)
class BaseEntity:
    """Base for all domain entities - pure Python, no database knowledge.
    
    Uses Result types from core layer for error handling.
    """
    id: UUID
    created_at: datetime
    updated_at: datetime
```

### Infrastructure Layer (Database Implementation)

**Location**: `src/infrastructure/persistence/`

**Responsibilities**:

- Provide concrete database implementations
- Handle database connections and sessions
- Convert between domain entities and database models

**Files**:

```text
src/infrastructure/persistence/
├── __init__.py
├── database.py          # Session management
├── base.py              # SQLAlchemy base model
├── models/              # Database models (SQLAlchemy/SQLModel)
│   ├── __init__.py
│   └── user.py          # Example: UserModel (NOT domain entity)
└── repositories/        # Concrete repository implementations
    ├── __init__.py
    └── user_repository.py  # Example: UserRepository
```

### Application Layer (Orchestration)

**Location**: `src/application/`

**Responsibilities**:

- Use repositories through protocols
- Orchestrate business workflows
- Handle transactions

**Example**:

```python
# src/application/services/user_service.py
class UserService:
    def __init__(
        self,
        user_repo: UserRepository,  # Protocol, not concrete class
        db: DatabaseProtocol,        # For transaction management
    ):
        self.user_repo = user_repo
        self.db = db
    
    async def register_user(self, email: str) -> User:
        async with self.db.transaction():
            # Business logic here
            user = User.create(email=email)
            await self.user_repo.save(user)
            return user
```

## Database Session Management

### Design Pattern: Async Context Manager

**Purpose**: Ensure proper session lifecycle management

```python
# src/infrastructure/persistence/database.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

class Database:
    """Database connection and session management.
    
    Responsibilities:
    - Create and manage database engine
    - Provide async sessions
    - Handle transaction boundaries
    """
    
    def __init__(self, database_url: str, **engine_kwargs):
        """Initialize database with connection URL.
        
        Args:
            database_url: PostgreSQL connection string
            **engine_kwargs: Additional engine configuration
        """
        self.engine = create_async_engine(
            database_url,
            echo=engine_kwargs.get("echo", False),
            pool_pre_ping=True,  # Verify connections before use
            pool_size=20,
            max_overflow=0,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional session.
        
        Yields:
            AsyncSession: Database session with automatic cleanup
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def transaction(self):
        """Provide explicit transaction boundary.
        
        Usage:
            async with db.transaction():
                await repo1.save(entity1)
                await repo2.save(entity2)
                # Both save in same transaction
        """
        async with self.get_session() as session:
            async with session.begin():
                yield session
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
```

### Centralized Dependency Injection

**Database uses the centralized container pattern** (see
`dependency-injection-architecture.md`):

```python
# src/core/container.py
from functools import lru_cache
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.persistence.database import Database
from src.core.config import settings

@lru_cache()
def get_database() -> Database:
    """Get database manager singleton (app-scoped).
    
    Returns Database instance with connection pool.
    Use get_db_session() for per-request sessions.
    
    Returns:
        Database manager instance.
    
    Note:
        This is rarely used directly. Prefer get_db_session() for sessions.
    """
    return Database(
        database_url=settings.database_url,
        echo=settings.db_echo,
    )

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (request-scoped).
    
    Creates new session per request with automatic transaction management:
        - Commits on success
        - Rolls back on exception
        - Always closes session
    
    Yields:
        Database session for request duration.
    
    Usage:
        # Presentation Layer (FastAPI endpoint)
        @router.post("/users")
        async def create_user(
            session: AsyncSession = Depends(get_db_session)
        ):
            # Use session
            ...
    """
    db = get_database()
    async with db.get_session() as session:
        yield session

# Usage in endpoints
@router.post("/users")
async def create_user(
    data: UserCreate,
    session: AsyncSession = Depends(get_db_session),
):
    # Session automatically managed
    ...
```

**Benefits of centralized pattern**:

- ✅ Single source of truth for all dependencies
- ✅ Easy to mock in tests (`patch("src.core.container.get_database")`)
- ✅ Clear lifecycle management (app-scoped vs request-scoped)
- ✅ Consistent with cache and secrets management

## Base Model Design

### SQLAlchemy Base with Timestamps

```python
# src/infrastructure/persistence/base.py
from datetime import datetime, timezone
from uuid_extensions import uuid7

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for all database models.
    
    Provides:
    - UUID primary key
    - created_at timestamp (UTC)
    - updated_at timestamp (UTC, auto-updates)
    """
    
    __abstract__ = True
    
    # Every model gets these fields
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<{self.__class__.__name__}(id={self.id})>"
```

## Alembic Migration Setup

### Async Alembic Configuration

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from src.infrastructure.persistence.base import Base
from src.core.config import settings

config = context.config

# Set database URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    
    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## Testing Strategy

### CRITICAL: Infrastructure Testing Philosophy

**Infrastructure adapters should be tested with integration tests, NOT unit tests.**

The Database class is a thin wrapper around SQLAlchemy. Unit testing it would require:

- Complex async mocking
- Mocking SQLAlchemy internals
- Testing framework behavior instead of our code

**This violates the testing pyramid principle and adds no value.**

### Testing by Layer

| Layer | Testing Strategy | Reasoning |
| ------- | ---------------- | ------------ |
| Domain | Heavy unit testing | Business logic lives here |
| Application | Unit tests with mocked repos | Use case orchestration |
| Infrastructure | Integration tests ONLY | Thin adapters around systems |
| Presentation | API/E2E tests | Full request/response flow |

### No Unit Tests for Database Infrastructure

**We explicitly DO NOT unit test the Database class because:**

1. It's a thin wrapper with no business logic
2. It delegates to SQLAlchemy
3. Mocking would test mock behavior, not real behavior
4. Integration tests provide actual value

### Integration Tests (Primary Testing Strategy)

**Integration tests are the ONLY tests for database infrastructure:**

```python
# tests/integration/test_infrastructure_persistence_database.py
import pytest
import pytest_asyncio
from sqlalchemy import text

from src.core.config import settings
from src.infrastructure.persistence.database import Database

@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database infrastructure."""
    
    @pytest_asyncio.fixture
    async def test_database(self):
        """Create test database connection.
        
        Uses settings from environment - no hardcoded values.
        """
        db = Database(
            database_url=settings.database_url,
            echo=settings.db_echo
        )
        yield db
        await db.close()
    
    @pytest.mark.asyncio
    async def test_database_connection_works(self, test_database):
        """Test that we can connect to the real database."""
        result = await test_database.check_connection()
        assert result == True

@pytest.mark.asyncio
@pytest.mark.integration
async def test_transaction_isolation():
    """Test transaction isolation and rollback."""
    db = Database(settings.database_url)
    
    try:
        # Start transaction that will be rolled back
        async with db.get_session() as session:
            await session.execute(
                text("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            )
            # Don't commit - let context manager handle it
        
        # Verify table exists
        async with db.get_session() as session:
            result = await session.execute(
                text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename='test_table')")
            )
            assert result.scalar() == True
        
        # Clean up
        async with db.get_session() as session:
            await session.execute(text("DROP TABLE test_table"))
    finally:
        await db.close()
```

## Common Anti-Patterns to Avoid

### ❌ Domain Importing Infrastructure

```python
# WRONG - Domain should not know about SQLAlchemy
# src/domain/entities/user.py
from sqlalchemy.orm import Mapped  # NO!
from src.infrastructure.persistence.base import Base  # NO!

class User(Base):  # Domain coupled to database!
    __tablename__ = "users"
    email: Mapped[str]
```

### ✅ Correct Separation

```python
# CORRECT - Domain is pure
# src/domain/entities/user.py
from dataclasses import dataclass
from uuid import UUID

@dataclass(slots=True, kw_only=True)
class User:
    """Pure domain entity."""
    id: UUID
    email: str
    
# src/infrastructure/persistence/models/user_model.py
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.persistence.base import Base
from src.domain.entities.user import User  # Import domain entity for conversion

class UserModel(Base):
    """Database model - infrastructure concern.
    
    This is a database model, NOT a domain entity.
    Lives in infrastructure layer, not domain.
    """
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(unique=True, index=True)
    
    def to_entity(self) -> User:
        """Convert to domain entity."""
        return User(id=self.id, email=self.email)
    
    @classmethod
    def from_entity(cls, user: User) -> "UserModel":
        """Create from domain entity."""
        return cls(id=user.id, email=user.email)
```

### ❌ Creating Dependencies Inside Classes

```python
# WRONG - Creates tight coupling
class UserService:
    def __init__(self):
        self.db = Database(settings.database_url)  # Creating dependency!
        self.session = self.db.get_session()  # Managing lifecycle!
```

### ✅ Correct Dependency Injection

```python
# CORRECT - Dependencies injected
class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session  # Injected, not created
```

### ❌ Business Logic in Repository

```python
# WRONG - Repository doing business logic
class UserRepository:
    async def create_user(self, email: str, password: str):
        # Business logic in repository!
        if not self.validate_email(email):
            raise ValueError("Invalid email")
        
        hashed = self.hash_password(password)
        # ...
```

### ✅ Repository Only Persists

```python
# CORRECT - Repository only handles persistence
class UserRepository:
    async def save(self, user: User) -> None:
        """Just save - no business logic."""
        model = UserModel.from_entity(user)
        self.session.add(model)
        await self.session.flush()
    
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Just fetch - no business logic."""
        result = await self.session.get(UserModel, user_id)
        return result.to_entity() if result else None
```

## Makefile Commands

```makefile
# Database management commands
migrate-create:
    @echo "Creating migration: $(NAME)"
    docker compose -f compose/docker-compose.dev.yml exec app \
        alembic revision --autogenerate -m "$(NAME)"

migrate-up:
    @echo "Applying migrations..."
    docker compose -f compose/docker-compose.dev.yml exec app \
        alembic upgrade head

migrate-down:
    @echo "Rolling back migration..."
    docker compose -f compose/docker-compose.dev.yml exec app \
        alembic downgrade -1

migrate-history:
    @echo "Migration history:"
    docker compose -f compose/docker-compose.dev.yml exec app \
        alembic history --verbose
```

## Environment Variables

Required in `.env` files:

```bash
# Database configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@dashtam-dev-postgres:5432/dashtam
DB_ECHO=false  # Set to true for SQL logging in development
```

## Success Criteria

- [ ] Database session management with proper lifecycle
- [ ] Base model with UUID and timestamps
- [ ] Alembic configured for async operations
- [ ] Domain stays pure (no database imports)
- [ ] Dependency injection throughout
- [ ] Integration with domain events (critical operations emit events)
- [ ] Integration with audit trail (all writes are audited)
- [ ] Integration with error handling (Result types, no exceptions)
- [ ] Integration with structured logging (all operations logged)
- [ ] Integration tests with real database (NO unit tests for infrastructure)
- [ ] All tests passing
- [ ] Documentation complete

---

## Summary

The database architecture is fully integrated with Dashtam's architecture ecosystem.

### Core Principles

1. **Hexagonal Architecture**: Database is infrastructure, domain defines protocols
2. **Dependency Injection**: No direct instantiation, dependencies injected
3. **SOLID Principles**: Each component has single responsibility
4. **Proper Testing**: Integration tests for infrastructure (NO unit tests)
5. **Async Throughout**: All database operations are async

### Architecture Integration

**Domain Events** (`/tmp/domain-events-architecture.md`):

- Critical database operations emit domain events
- Events trigger audit, logging, notifications, and side effects
- Decoupled through event bus (publishers don't know subscribers)

**Audit Trail** (`/tmp/audit-trail-architecture.md`):

- All write operations are audited (WHO, WHAT, WHEN, WHERE)
- Audit logs are immutable with 7+ year retention (compliance)
- Separate from technical logging (different purpose, storage, retention)

**Error Handling** (`/tmp/error-handling-architecture.md`):

- Database operations return Result types (Success/Failure)
- No exceptions thrown to domain layer
- Errors mapped: SQLAlchemy exceptions → Domain errors → RFC 7807

**Structured Logging** (`/tmp/structured-logging-architecture.md`):

- All database operations logged with trace IDs
- Environment-aware: Console (dev) → CloudWatch (production)
- Separate from audit trail (technical vs compliance)

### Database Operation Flow

```mermaid
sequenceDiagram
    participant API as API Endpoint
    participant App as Application Service
    participant Repo as Repository
    participant DB as Database
    participant Events as Event Bus
    participant Audit as Audit Service
    participant Log as Logger

    API->>App: Command/Query
    App->>Repo: Database operation
    Repo->>Log: Log operation start
    Repo->>DB: Execute SQL
    DB-->>Repo: Result/Error
    
    alt Success
        Repo->>Log: Log success
        Repo-->>App: Success(data)
        App->>Events: Publish event (if critical)
        Events->>Audit: Record audit trail
        Events->>Log: Log event
    else Failure
        Repo->>Log: Log error
        Repo-->>App: Failure(error)
        App->>Audit: Record failure
    end
    
    App-->>API: Result
```

This ensures our database layer is:

- **Decoupled**: Domain doesn't know about database
- **Observable**: Full logging and tracing
- **Auditable**: Complete audit trail for compliance
- **Event-Driven**: Critical operations trigger workflows
- **Resilient**: Explicit error handling with Result types
- **Testable**: Can mock for unit tests
- **Flexible**: Can switch database implementations
- **Maintainable**: Clear separation of concerns
- **Centralized DI**: Uses container pattern for consistent dependency management

---

### Key Lessons Learned

1. **Don't unit test infrastructure adapters**: Complex mocking, no value
2. **Use settings for all configuration**: No hardcoded database URLs
3. **Keep domain pure**: BaseModel belongs in infrastructure, not domain
4. **Integration tests are sufficient**: For thin wrappers around externals
5. **Follow the checklist**: Would have caught the testing issue earlier
6. **Centralized dependencies**: Use container pattern for all infrastructure

**See also**: `dependency-injection-architecture.md` for container pattern details.

---

**Created**: 2025-11-09 | **Last Updated**: 2025-11-13
