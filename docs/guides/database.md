# Database Usage Guide

Practical how-to patterns for working with the database layer in Dashtam.

**Architecture Reference**: `docs/architecture/database.md`

---

## Quick Start

### Get a Database Session

```python
from src.core.container import get_db_session

# In FastAPI endpoint (recommended)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

@router.post("/users")
async def create_user(
    data: UserCreate,
    session: AsyncSession = Depends(get_db_session)
):
    # Session automatically commits on success, rolls back on error
    user_repo = UserRepository(session)
    user = await user_repo.save(user_entity)
    return UserResponse.from_entity(user)
```

### Direct Session Access (Application Layer)

```python
from src.core.container import get_database

db = get_database()

async with db.get_session() as session:
    # Use session
    result = await session.execute(text("SELECT 1"))
```

---

## Session Management

### Automatic Transaction Management

The `get_session()` context manager handles transactions automatically:

```python
async with db.get_session() as session:
    # Operations here
    user_repo = UserRepository(session)
    await user_repo.save(user)
    # Commits automatically on successful exit

# If exception occurs:
# - Rolls back automatically
# - Re-raises the exception
```

### Explicit Transaction Control

For operations spanning multiple repositories:

```python
async with db.transaction() as session:
    user_repo = UserRepository(session)
    account_repo = AccountRepository(session)
    
    await user_repo.save(user)
    await account_repo.save(account)
    # Both commit together or both roll back
```

---

## Creating Models

### Mutable Model (can be updated)

```python
# src/infrastructure/persistence/models/user.py
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.persistence.base import BaseMutableModel

class UserModel(BaseMutableModel):
    """User database model.
    
    Inherits from BaseMutableModel:
        - id: UUID (auto-generated)
        - created_at: datetime (auto-set)
        - updated_at: datetime (auto-updated)
    """
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
```

### Immutable Model (audit logs, events)

```python
# src/infrastructure/persistence/models/audit_log.py
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.persistence.base import BaseModel

class AuditLogModel(BaseModel):
    """Audit log - immutable (no updated_at).
    
    Inherits from BaseModel:
        - id: UUID (auto-generated)
        - created_at: datetime (auto-set)
    """
    __tablename__ = "audit_logs"
    
    action: Mapped[str]
    user_id: Mapped[UUID]
    resource_type: Mapped[str]
    # No updated_at - audit logs are immutable
```

---

## Repository Pattern

### Creating a Repository

```python
# src/infrastructure/persistence/repositories/user_repository.py
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.infrastructure.persistence.models.user import UserModel

class UserRepository:
    """Repository for User persistence.
    
    Maps between domain entities and database models.
    NO business logic - just persistence operations.
    """
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def save(self, user: User) -> User:
        """Save user entity to database."""
        model = UserModel.from_entity(user)
        self._session.add(model)
        await self._session.flush()  # Get generated ID
        return model.to_entity()
    
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID."""
        model = await self._session.get(UserModel, user_id)
        return model.to_entity() if model else None
    
    async def find_by_email(self, email: str) -> User | None:
        """Find user by email."""
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def delete(self, user: User) -> None:
        """Delete user from database."""
        model = await self._session.get(UserModel, user.id)
        if model:
            await self._session.delete(model)
```

### Entity-Model Mapping

```python
# In UserModel class
def to_entity(self) -> User:
    """Convert database model to domain entity."""
    return User(
        id=self.id,
        email=self.email,
        password_hash=self.password_hash,
        is_active=self.is_active,
        created_at=self.created_at,
        updated_at=self.updated_at,
    )

@classmethod
def from_entity(cls, user: User) -> "UserModel":
    """Create database model from domain entity."""
    return cls(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        is_active=user.is_active,
    )
```

---

## Alembic Migrations

### Create a New Migration

```bash
# Create migration with auto-generated changes
make migrate-create NAME="add_users_table"

# Or in Docker:
docker compose -f compose/docker-compose.dev.yml exec app \
    alembic revision --autogenerate -m "add_users_table"
```

### Apply Migrations

```bash
make migrate-up

# Or in Docker:
docker compose -f compose/docker-compose.dev.yml exec app \
    alembic upgrade head
```

### Rollback Migration

```bash
make migrate-down

# Or in Docker:
docker compose -f compose/docker-compose.dev.yml exec app \
    alembic downgrade -1
```

### View Migration History

```bash
make migrate-history
```

---

## Testing

### Integration Tests (Recommended)

```python
# tests/integration/test_user_repository.py
import pytest
import pytest_asyncio
from src.core.config import settings
from src.infrastructure.persistence.database import Database

@pytest.mark.integration
class TestUserRepository:
    
    @pytest_asyncio.fixture
    async def db(self):
        """Create test database connection."""
        database = Database(
            database_url=settings.database_url,
            echo=settings.db_echo
        )
        yield database
        await database.close()
    
    @pytest.mark.asyncio
    async def test_save_and_find_user(self, db):
        """Test saving and retrieving a user."""
        async with db.get_session() as session:
            repo = UserRepository(session)
            
            user = User(
                id=uuid7(),
                email="test@example.com",
                password_hash="hashed",
            )
            
            saved = await repo.save(user)
            assert saved.id == user.id
            
            found = await repo.find_by_email("test@example.com")
            assert found is not None
            assert found.email == "test@example.com"
```

### Mocking for Unit Tests

```python
# tests/unit/test_user_service.py
from unittest.mock import AsyncMock, Mock

def test_register_user():
    """Unit test with mocked repository."""
    # Mock repository
    mock_repo = Mock()
    mock_repo.save = AsyncMock(return_value=user)
    mock_repo.find_by_email = AsyncMock(return_value=None)
    
    service = UserService(user_repo=mock_repo)
    
    result = await service.register(email="test@example.com")
    
    assert result.is_success()
    mock_repo.save.assert_called_once()
```

---

## Common Patterns

### Pattern 1: Handler with Repository

```python
# src/application/commands/register_user.py
from src.domain.protocols.user_repository import UserRepository

class RegisterUserHandler:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo
    
    async def handle(self, cmd: RegisterUser) -> Result[UUID, Error]:
        # Check if email exists
        existing = await self._user_repo.find_by_email(cmd.email)
        if existing:
            return Failure(ValidationError("Email already registered"))
        
        # Create and save user
        user = User.create(email=cmd.email, password_hash=cmd.hashed_password)
        await self._user_repo.save(user)
        
        return Success(user.id)
```

### Pattern 2: Query with Pagination

```python
async def find_all_paginated(
    self,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """Find all users with pagination."""
    # Count total
    count_stmt = select(func.count()).select_from(UserModel)
    total = (await self._session.execute(count_stmt)).scalar() or 0
    
    # Get page
    offset = (page - 1) * page_size
    stmt = select(UserModel).offset(offset).limit(page_size)
    result = await self._session.execute(stmt)
    
    users = [model.to_entity() for model in result.scalars()]
    return users, total
```

### Pattern 3: Soft Delete

```python
# In model
is_deleted: Mapped[bool] = mapped_column(default=False)
deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

# In repository
async def soft_delete(self, user_id: UUID) -> None:
    """Mark user as deleted (soft delete)."""
    stmt = (
        update(UserModel)
        .where(UserModel.id == user_id)
        .values(is_deleted=True, deleted_at=func.now())
    )
    await self._session.execute(stmt)
```

---

## Troubleshooting

### Connection Issues

**Symptoms**: `ConnectionRefusedError` or timeout errors

**Solutions**:

1. Check database container is running: `docker ps`
2. Verify `DATABASE_URL` in `.env` file
3. Check database logs: `docker compose logs postgres`

### Migration Conflicts

**Symptoms**: `Can't locate revision` or head mismatch

**Solutions**:

```bash
# Check current state
alembic current

# Stamp to specific revision
alembic stamp head

# Generate new migration from current state
alembic revision --autogenerate -m "sync_schema"
```

### Session Already Closed

**Symptoms**: `Session is closed` error

**Solutions**:

1. Ensure using `async with db.get_session()` pattern
2. Don't store session references beyond context manager scope
3. Use `expire_on_commit=False` (already configured)

---

**See Also**:

- `docs/architecture/database.md` - Full architecture details
- `docs/architecture/dependency-injection.md` - Container patterns

---

**Created**: 2025-12-05 | **Last Updated**: 2025-12-05
