# Protocol-Based Architecture

## Overview

**Purpose**: Use Python `Protocol` for structural typing to define interfaces without inheritance, enabling flexible, testable, and Pythonic code.

**Problem**: Traditional ABC (Abstract Base Classes) create tight coupling:

- Concrete classes must inherit from ABC (nominal typing)
- Hard to test (must inherit to satisfy type checker)
- Not Pythonic (duck typing is preferred in Python)
- Difficult to adapt third-party code
- Coupling between interface definition and implementation

**Solution**: Protocol-based architecture using Python `Protocol`:

- **Structural typing**: Classes satisfy protocols by shape, not inheritance
- **No inheritance required**: Duck typing with type safety
- **Easy testing**: Mock objects don't need inheritance
- **Pythonic**: Aligns with Python's philosophy
- **Framework independence**: Third-party code can satisfy protocols

---

## Core Concepts

### 1. Structural Typing vs Nominal Typing

**Nominal Typing** (ABC): Class must explicitly inherit to satisfy interface.

```python
# Nominal typing with ABC
from abc import ABC, abstractmethod

class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None:
        pass

class RedisCache(CacheBackend):  # MUST inherit
    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)
```

**Structural Typing** (Protocol): Class satisfies interface by having correct method signatures.

```python
# Structural typing with Protocol
from typing import Protocol

class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None:
        """Get value by key."""
        ...

class RedisCache:  # NO inheritance needed!
    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

# RedisCache satisfies CacheProtocol automatically (duck typing)
```

**Key Difference**: Protocol checks **shape** (method signatures), ABC checks **inheritance** (class hierarchy).

### 2. Why Protocol Over ABC?

#### Pythonic Philosophy

Python embraces **duck typing**: "If it walks like a duck and quacks like a duck, it's a duck."

```python
# Duck typing in Python
def process(items):
    for item in items:
        print(item)

# Works with list, tuple, set, generator - no inheritance needed!
process([1, 2, 3])
process((1, 2, 3))
process({1, 2, 3})
```

**Protocol extends duck typing with type safety**:

```python
from typing import Protocol

class Iterable(Protocol):
    def __iter__(self):
        ...

def process(items: Iterable):  # Type-checked duck typing
    for item in items:
        print(item)
```

#### No Inheritance Required

**ABC Problem**:

```python
class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None:
        pass

# MUST inherit to satisfy type checker
class RedisCache(CacheBackend):
    ...

# Can't adapt third-party library without wrapper
from third_party import TheirCache  # Can't make this inherit CacheBackend
```

**Protocol Solution**:

```python
class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None:
        ...

# NO inheritance needed
class RedisCache:
    async def get(self, key: str) -> str | None:
        ...

# Third-party code works if it has correct shape
from third_party import TheirCache  # Works if it has get() method!
```

#### Easy Testing

**ABC Problem**:

```python
# Mock MUST inherit to satisfy mypy
class MockCache(CacheBackend):  # Inheritance required
    async def get(self, key: str) -> str | None:
        return "mocked"
```

**Protocol Solution**:

```python
# Mock doesn't need inheritance
class MockCache:  # No inheritance!
    async def get(self, key: str) -> str | None:
        return "mocked"

# Or use unittest.mock.AsyncMock with spec
mock = AsyncMock(spec=CacheProtocol)
```

#### Framework Independence

**Protocol allows domain to define interfaces without coupling to implementation**:

```python
# Domain defines port (Protocol)
class UserRepository(Protocol):
    async def save(self, user: User) -> None: ...

# Infrastructure implements adapter (no inheritance)
class PostgresUserRepository:  # No coupling to domain!
    async def save(self, user: User) -> None:
        # PostgreSQL implementation
        ...
```

**This is the foundation of Hexagonal Architecture**: Domain defines ports, infrastructure provides adapters.

### 3. Protocol Syntax

**Basic Protocol**:

```python
from typing import Protocol

class Drawable(Protocol):
    """Protocol for objects that can be drawn."""
    
    def draw(self) -> None:
        """Draw the object."""
        ...
```

**Protocol with Methods and Properties**:

```python
from typing import Protocol

class Sized(Protocol):
    """Protocol for objects with size."""
    
    @property
    def size(self) -> int:
        """Object size."""
        ...
    
    def resize(self, new_size: int) -> None:
        """Resize object."""
        ...
```

**Generic Protocol**:

```python
from typing import Protocol, TypeVar

T = TypeVar("T")

class Container(Protocol[T]):
    """Generic container protocol."""
    
    def add(self, item: T) -> None:
        """Add item to container."""
        ...
    
    def get(self, index: int) -> T:
        """Get item by index."""
        ...
```

**Protocol with Async Methods**:

```python
from typing import Protocol

class AsyncRepository(Protocol):
    """Protocol for async repository operations."""
    
    async def find_by_id(self, id: str) -> object | None:
        """Find entity by ID."""
        ...
    
    async def save(self, entity: object) -> None:
        """Save entity."""
        ...
```

---

## Protocol Implementations in Dashtam

### Repository Protocols

**Port (Domain Layer)**:

```python
# src/domain/protocols/user_repository.py
from typing import Protocol
from uuid import UUID
from src.domain.entities.user import User

class UserRepository(Protocol):
    """Repository port for user persistence.
    
    Implementations must provide async methods for user CRUD operations.
    All methods return domain entities, not database models.
    """
    
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID.
        
        Args:
            user_id: User identifier.
            
        Returns:
            User entity if found, None otherwise.
        """
        ...
    
    async def find_by_email(self, email: str) -> User | None:
        """Find user by email address.
        
        Args:
            email: User's email address.
            
        Returns:
            User entity if found, None otherwise.
        """
        ...
    
    async def save(self, user: User) -> None:
        """Persist user entity.
        
        Args:
            user: User entity to persist.
        """
        ...
    
    async def delete(self, user_id: UUID) -> None:
        """Delete user by ID.
        
        Args:
            user_id: User identifier.
        """
        ...
```

**Adapter (Infrastructure Layer)**:

```python
# src/infrastructure/persistence/repositories/user_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID

from src.domain.entities.user import User
from src.infrastructure.persistence.models.user import UserModel

class UserRepository:  # NO inheritance!
    """PostgreSQL adapter for UserRepository port.
    
    Implements UserRepository protocol via structural typing.
    Handles mapping between domain entities and database models.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.
        
        Args:
            session: SQLAlchemy async session.
        """
        self._session = session
    
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID in PostgreSQL."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_entity(model)
    
    async def find_by_email(self, email: str) -> User | None:
        """Find user by email in PostgreSQL."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_entity(model)
    
    async def save(self, user: User) -> None:
        """Persist user entity to PostgreSQL."""
        existing = await self._session.get(UserModel, user.id)
        
        if existing:
            # Update
            existing.email = user.email
            existing.is_verified = user.is_verified
        else:
            # Insert
            model = self._to_model(user)
            self._session.add(model)
        
        await self._session.flush()
    
    async def delete(self, user_id: UUID) -> None:
        """Delete user from PostgreSQL."""
        await self._session.execute(
            delete(UserModel).where(UserModel.id == user_id)
        )
        await self._session.flush()
    
    def _to_entity(self, model: UserModel) -> User:
        """Map database model to domain entity."""
        return User(
            id=model.id,
            email=model.email,
            is_verified=model.is_verified,
        )
    
    def _to_model(self, user: User) -> UserModel:
        """Map domain entity to database model."""
        return UserModel(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
        )
```

**Key Points**:

- ✅ `UserRepository` class has NO inheritance
- ✅ Satisfies `UserRepository` protocol by having correct method signatures
- ✅ mypy verifies compatibility at type-check time
- ✅ Easy to swap implementations (PostgreSQL → MongoDB)

### Service Protocols

**Cache Protocol**:

```python
# src/domain/protocols/cache_protocol.py
from typing import Protocol
from src.core.result import Result
from src.core.errors import DomainError

class CacheProtocol(Protocol):
    """Protocol for cache operations.
    
    Implementations provide key-value storage with TTL support.
    All operations return Result types for explicit error handling.
    """
    
    async def get(self, key: str) -> Result[str | None, DomainError]:
        """Get value by key.
        
        Args:
            key: Cache key.
            
        Returns:
            Success(value) if key exists, Success(None) if not found,
            Failure(error) on cache failure.
        """
        ...
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> Result[None, DomainError]:
        """Set key-value pair with optional TTL.
        
        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds (None = no expiry).
            
        Returns:
            Success(None) on success, Failure(error) on cache failure.
        """
        ...
    
    async def delete(self, key: str) -> Result[None, DomainError]:
        """Delete key from cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Success(None) on success, Failure(error) on cache failure.
        """
        ...
    
    async def delete_pattern(self, pattern: str) -> Result[int, DomainError]:
        """Delete all keys matching pattern.
        
        Args:
            pattern: Pattern to match (e.g., "user:*").
            
        Returns:
            Success(deleted_count), Failure(error) on cache failure.
        """
        ...
```

**Redis Adapter**:

```python
# src/infrastructure/cache/redis_adapter.py
from redis.asyncio import Redis
from src.core.result import Result, Success, Failure
from src.core.errors import DomainError

class RedisAdapter:  # NO inheritance!
    """Redis implementation of CacheProtocol."""
    
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
    
    async def get(self, key: str) -> Result[str | None, DomainError]:
        """Get value from Redis."""
        try:
            value = await self._redis.get(key)
            return Success(value=value.decode() if value else None)
        except Exception as e:
            return Failure(error=DomainError(message=str(e)))
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> Result[None, DomainError]:
        """Set value in Redis."""
        try:
            await self._redis.set(key, value, ex=ttl)
            return Success(value=None)
        except Exception as e:
            return Failure(error=DomainError(message=str(e)))
    
    async def delete(self, key: str) -> Result[None, DomainError]:
        """Delete key from Redis."""
        try:
            await self._redis.delete(key)
            return Success(value=None)
        except Exception as e:
            return Failure(error=DomainError(message=str(e)))
    
    async def delete_pattern(self, pattern: str) -> Result[int, DomainError]:
        """Delete keys matching pattern from Redis."""
        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self._redis.delete(*keys)
            else:
                deleted = 0
            
            return Success(value=deleted)
        except Exception as e:
            return Failure(error=DomainError(message=str(e)))
```

### Provider Protocols

**Provider Protocol**:

```python
# src/domain/protocols/provider_protocol.py
from typing import Protocol
from src.core.result import Result
from src.domain.entities.account import Account
from src.domain.entities.transaction import Transaction
from src.domain.errors.provider_error import ProviderError

class ProviderProtocol(Protocol):
    """Protocol for financial provider adapters.
    
    Implementations integrate with financial institutions (brokerages, banks)
    to fetch account and transaction data. All methods return Result types.
    """
    
    async def fetch_accounts(
        self,
        credentials: dict[str, str],
    ) -> Result[list[Account], ProviderError]:
        """Fetch all accounts from provider.
        
        Args:
            credentials: Provider-specific credentials (OAuth tokens, API keys, etc.).
            
        Returns:
            Success(accounts) with domain Account entities,
            Failure(error) on provider API failure.
        """
        ...
    
    async def fetch_transactions(
        self,
        credentials: dict[str, str],
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Result[list[Transaction], ProviderError]:
        """Fetch transactions for account.
        
        Args:
            credentials: Provider-specific credentials.
            account_id: Provider's account identifier.
            start_date: Start date (ISO format, optional).
            end_date: End date (ISO format, optional).
            
        Returns:
            Success(transactions) with domain Transaction entities,
            Failure(error) on provider API failure.
        """
        ...
```

**Schwab Provider Adapter**:

```python
# src/infrastructure/providers/schwab/schwab_provider.py
from src.core.result import Result, Success, Failure
from src.domain.entities.account import Account
from src.domain.entities.transaction import Transaction
from src.domain.errors.provider_error import ProviderError
from src.infrastructure.providers.schwab.api_client import SchwabAPIClient
from src.infrastructure.providers.schwab.mappers import (
    SchwabAccountMapper,
    SchwabTransactionMapper,
)

class SchwabProvider:  # NO inheritance!
    """Charles Schwab provider adapter.
    
    Implements ProviderProtocol for Schwab brokerage integration.
    """
    
    def __init__(
        self,
        api_client: SchwabAPIClient,
        account_mapper: SchwabAccountMapper,
        transaction_mapper: SchwabTransactionMapper,
    ) -> None:
        self._api_client = api_client
        self._account_mapper = account_mapper
        self._transaction_mapper = transaction_mapper
    
    async def fetch_accounts(
        self,
        credentials: dict[str, str],
    ) -> Result[list[Account], ProviderError]:
        """Fetch accounts from Schwab API."""
        access_token = credentials.get("access_token")
        
        if not access_token:
            return Failure(
                error=ProviderError(message="Missing access_token")
            )
        
        # Call Schwab API
        result = await self._api_client.get_accounts(access_token)
        
        if isinstance(result, Failure):
            return result
        
        # Map Schwab response → domain Account entities
        schwab_accounts = result.value
        accounts = [
            self._account_mapper.map(acc) for acc in schwab_accounts
        ]
        
        return Success(value=accounts)
    
    async def fetch_transactions(
        self,
        credentials: dict[str, str],
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Result[list[Transaction], ProviderError]:
        """Fetch transactions from Schwab API."""
        access_token = credentials.get("access_token")
        
        if not access_token:
            return Failure(
                error=ProviderError(message="Missing access_token")
            )
        
        # Call Schwab API
        result = await self._api_client.get_transactions(
            access_token=access_token,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        if isinstance(result, Failure):
            return result
        
        # Map Schwab response → domain Transaction entities
        schwab_transactions = result.value
        transactions = [
            self._transaction_mapper.map(txn) for txn in schwab_transactions
        ]
        
        return Success(value=transactions)
```

---

## Protocol vs Inheritance: Decision Matrix

### When to Use Protocol

**Use Protocol for**:

✅ **Interfaces with multiple implementations**

```python
class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None: ...

# Multiple implementations
class RedisCache: ...
class MemcachedCache: ...
class InMemoryCache: ...
```

✅ **Domain ports (Hexagonal Architecture)**

```python
# Domain defines port
class UserRepository(Protocol):
    async def save(self, user: User) -> None: ...

# Infrastructure provides adapter
class PostgresUserRepository: ...
```

✅ **Third-party integration**

```python
# Adapt third-party library without wrapper
class FileSystem(Protocol):
    def read(self, path: str) -> str: ...

# Works with any object that has read()
import os  # os module satisfies protocol!
```

✅ **Testing with mocks**

```python
# Easy mocking without inheritance
mock = AsyncMock(spec=CacheProtocol)
```

### When to Use Inheritance

**Use Inheritance for**:

✅ **Data structures sharing fields**

```python
@dataclass(frozen=True, kw_only=True)
class DomainError:
    code: ErrorCode
    message: str

class ValidationError(DomainError):  # Inherits fields
    field: str | None = None
```

✅ **Domain events**

```python
@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: UUID
    occurred_at: datetime

class UserRegistered(DomainEvent):  # Inherits event metadata
    user_id: UUID
    email: str
```

✅ **Commands/Queries (shared structure)**

```python
# Base structure for all commands
@dataclass(frozen=True, kw_only=True)
class Command:
    pass

class RegisterUser(Command):
    email: str
    password: str
```

### Decision Table

| Use Case | Pattern | Example |
|----------|---------|---------|
| Repository interfaces | **Protocol** | UserRepository, AccountRepository |
| Service interfaces | **Protocol** | CacheProtocol, LoggerProtocol |
| Provider adapters | **Protocol** | ProviderProtocol |
| Error hierarchies | **Inheritance** | DomainError → ValidationError |
| Domain events | **Inheritance** | DomainEvent → UserRegistered |
| Commands/Queries | **Inheritance** | Command → RegisterUser |

---

## Testing with Protocols

### Unit Testing with Mocks

#### Example: Test handler with mocked repository protocol

```python
# tests/unit/test_application_register_user_handler.py
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.commands.auth_commands import RegisterUser
from src.application.commands.handlers.register_user_handler import (
    RegisterUserHandler,
)
from src.core.result import Success
from src.domain.entities.user import User


@pytest.mark.unit
class TestRegisterUserHandler:
    @pytest.mark.asyncio
    async def test_register_user_success():
        """Test successful user registration."""
        # Arrange - mock all 4 required dependencies
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None
        
        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed_password"
        mock_event_bus = AsyncMock()
        
        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )
        
        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )
        
        # Act
        result = await handler.handle(command)
        
        # Assert
        assert isinstance(result, Success)
        assert isinstance(result.value, UUID)
        
        # Verify repository called
        mock_user_repo.save.assert_called_once()
        saved_user = mock_user_repo.save.call_args[0][0]
        assert isinstance(saved_user, User)
        assert saved_user.email == "test@example.com"
```

**Key Benefits**:

- ✅ `AsyncMock()` creates flexible mocks for all protocol methods
- ✅ NO inheritance required for mock
- ✅ Class-based test organization with `@pytest.mark.unit`
- ✅ Command objects separate input data from handler logic

### Integration Testing with Real Adapters

#### Example: Test real adapter implements protocol correctly

```python
# tests/integration/test_user_repository.py
from datetime import UTC, datetime

import pytest
from uuid_extensions import uuid7

from src.domain.entities.user import User
from src.infrastructure.persistence.repositories.user_repository import (
    UserRepository,
)


@pytest.mark.integration
class TestUserRepositorySave:
    @pytest.mark.asyncio
    async def test_user_repository_save_and_find(self, test_database):
        """Verify UserRepository implements protocol correctly."""
        # Arrange - create user with ALL required fields
        user_id = uuid7()
        now = datetime.now(UTC)
        user = User(
            id=user_id,
            email=f"test_{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=False,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
            created_at=now,
            updated_at=now,
        )
        
        # Act - save using context manager pattern
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            await repo.save(user)
            await session.commit()
        
        # Assert - use separate session to verify persistence
        async with test_database.get_session() as session:
            repo = UserRepository(session=session)
            found = await repo.find_by_id(user_id)
        
        assert found is not None
        assert found.id == user_id
        assert found.email == user.email
```

### Type Checking with mypy

**mypy verifies protocol compatibility**:

```python
# Domain handler depends on protocol
class RegisterUserHandler:
    def __init__(self, user_repo: UserRepository):  # Protocol!
        self._user_repo = user_repo

# mypy verifies adapter satisfies protocol
repo = PostgresUserRepository(session=session)
handler = RegisterUserHandler(user_repo=repo)  # ✅ Type-safe

# mypy catches mismatches
class BrokenRepo:
    async def save(self, user: User, extra: int) -> None:  # Wrong signature!
        pass

handler = RegisterUserHandler(user_repo=BrokenRepo())  # ❌ mypy error!
```

---

## Common Pitfalls and Solutions

### ❌ Pitfall 1: Forgetting `...` in Protocol Methods

```python
# WRONG: No implementation marker
class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None:
        pass  # Should be `...`

# CORRECT: Use `...` (ellipsis)
class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None:
        ...
```

**Why**: `...` signals "no implementation" (protocol definition), `pass` is valid but less clear.

### ❌ Pitfall 2: Incorrect Method Signature

```python
# Protocol defines method
class UserRepository(Protocol):
    async def find_by_id(self, user_id: UUID) -> User | None:
        ...

# WRONG: Missing async
class PostgresUserRepository:
    def find_by_id(self, user_id: UUID) -> User | None:  # Not async!
        ...

# mypy error: Method signature doesn't match protocol
```

**Fix**: Match signatures exactly (including `async`, parameters, return type).

### ❌ Pitfall 3: Protocol with `kw_only` and mypy

```python
# Protocol uses kw_only
@dataclass(frozen=True, kw_only=True)
class Success:
    value: Any

# mypy reports error with positional pattern matching
match result:
    case Success(value):  # Error: requires keyword argument
        ...

# Fix: Use isinstance() instead
if isinstance(result, Failure):
    # Handle failure
    ...

# Type narrowing gives us Success
value = result.value
```

**See**: WARP.md Section 4 (Pattern Matching with kw_only Dataclasses).

### ❌ Pitfall 4: Protocol Import Cycles

```python
# domain/protocols/user_repository.py
from src.domain.entities.user import User  # Import entity

class UserRepository(Protocol):
    async def save(self, user: User) -> None:
        ...

# domain/entities/user.py
from src.domain.protocols.user_repository import UserRepository  # Cycle!
```

**Fix**: Don't import protocols into entities. Entities don't need repository references.

### ❌ Pitfall 5: Not Using `spec` in Mocks

```python
# WRONG: No spec, no type safety
mock_repo = AsyncMock()  # Any method call accepted!
mock_repo.non_existent_method()  # No error!

# CORRECT: Use spec
mock_repo = AsyncMock(spec=UserRepository)
mock_repo.non_existent_method()  # AttributeError!
```

---

## Protocol Best Practices

### 1. Keep Protocols Focused

**Good**: Single responsibility

```python
class UserRepository(Protocol):
    """User persistence only."""
    async def find_by_id(self, user_id: UUID) -> User | None: ...
    async def save(self, user: User) -> None: ...
```

**Bad**: Mixed responsibilities

```python
class UserManager(Protocol):  # Too broad!
    async def find_by_id(self, user_id: UUID) -> User | None: ...
    async def send_email(self, user: User) -> None: ...  # Different concern!
    async def log_activity(self, user: User) -> None: ...  # Different concern!
```

### 2. Use Google-Style Docstrings

**Every protocol method should document**:

- Purpose
- Parameters
- Return value
- Expected behavior

```python
class CacheProtocol(Protocol):
    """Protocol for cache operations."""
    
    async def get(self, key: str) -> Result[str | None, DomainError]:
        """Get value by key.
        
        Args:
            key: Cache key.
            
        Returns:
            Success(value) if key exists, Success(None) if key not found,
            Failure(error) on cache system failure.
        """
        ...
```

### 3. Location: `src/domain/protocols/`

**ALL protocols in one place** (Protocol consolidation):

```text
src/domain/protocols/
├── user_repository.py
├── account_repository.py
├── cache_protocol.py
├── logger_protocol.py
├── provider_protocol.py
└── ...
```

**See**: `directory-structure.md` for protocol consolidation rationale.

### 4. Naming Convention

**Repositories**: `{Entity}Repository` (e.g., `UserRepository`, `AccountRepository`)  
**Services**: `{Service}Protocol` (e.g., `CacheProtocol`, `LoggerProtocol`)  
**Adapters**: `{Provider}Protocol` (e.g., `ProviderProtocol`, `EmailProtocol`)

### 5. Result Types for Error Handling

**Protocols return Result types** (Railway-Oriented Programming):

```python
class CacheProtocol(Protocol):
    async def get(self, key: str) -> Result[str | None, DomainError]:
        """Return Success or Failure, never raise."""
        ...
```

**See**: `error-handling.md` for Result types.

### 6. Protocol Exports

**Export all protocols from `__init__.py`**:

```python
# src/domain/protocols/__init__.py
from src.domain.protocols.user_repository import UserRepository
from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.protocols.logger_protocol import LoggerProtocol

__all__ = [
    "UserRepository",
    "CacheProtocol",
    "LoggerProtocol",
]
```

---

## Integration with Hexagonal Architecture

**Protocols are the "Ports" in Hexagonal Architecture**:

```text
┌─────────────────────────────────────────┐
│ Domain Layer (Core)                     │
│                                         │
│ Protocols (Ports) ←─────────────┐      │
│ - UserRepository                 │      │
│ - CacheProtocol                  │      │
│ - ProviderProtocol               │      │
└─────────────────────────────────────────┘
          ↑ implements                      
          │                                 
┌─────────────────────────────────────────┐
│ Infrastructure Layer (Adapters)         │
│                                         │
│ Adapters (Implementations)              │
│ - PostgresUserRepository                │
│ - RedisCache                            │
│ - SchwabProvider                        │
└─────────────────────────────────────────┘
```

**Flow**:

1. Domain defines **port** (Protocol)
2. Infrastructure implements **adapter** (concrete class)
3. Application depends on **port**, receives **adapter** via DI
4. No coupling: Domain doesn't know about infrastructure

**See**: `hexagonal.md` for complete hexagonal architecture details.

---

## Real-World Examples from Dashtam

### Example 1: Cache Protocol

**Port**:

```python
# src/domain/protocols/cache_protocol.py
class CacheProtocol(Protocol):
    async def get(self, key: str) -> Result[str | None, DomainError]: ...
    async def set(self, key: str, value: str, ttl: int | None) -> Result[None, DomainError]: ...
```

**Adapter**:

```python
# src/infrastructure/cache/redis_adapter.py
class RedisAdapter:  # Implements CacheProtocol
    async def get(self, key: str) -> Result[str | None, DomainError]:
        # Redis implementation
        ...
```

**Usage**:

```python
# Handler depends on protocol
class SyncAccountsHandler:
    def __init__(self, cache: CacheProtocol):  # Port!
        self._cache = cache

# DI container injects adapter
from src.core.container import get_cache
cache = get_cache()  # Returns RedisAdapter
```

### Example 2: Authorization Protocol

**Port**:

```python
# src/domain/protocols/authorization_protocol.py
class AuthorizationProtocol(Protocol):
    async def check_permission(
        self,
        user_id: UUID,
        permission: Permission,
    ) -> Result[bool, DomainError]:
        ...
```

**Adapter**:

```python
# src/infrastructure/authorization/casbin_adapter.py
class CasbinAdapter:  # Implements AuthorizationProtocol
    async def check_permission(
        self,
        user_id: UUID,
        permission: Permission,
    ) -> Result[bool, DomainError]:
        # Casbin RBAC implementation
        ...
```

### Example 3: Provider Protocol (Multi-Provider)

**Port**:

```python
# src/domain/protocols/provider_protocol.py
class ProviderProtocol(Protocol):
    async def fetch_accounts(
        self,
        credentials: dict[str, str],
    ) -> Result[list[Account], ProviderError]:
        ...
```

**Multiple Adapters**:

```python
# Schwab adapter
class SchwabProvider:  # OAuth-based
    async def fetch_accounts(self, credentials):
        access_token = credentials["access_token"]
        # Schwab API call
        ...

# Alpaca adapter
class AlpacaProvider:  # API Key-based
    async def fetch_accounts(self, credentials):
        api_key = credentials["api_key"]
        api_secret = credentials["api_secret"]
        # Alpaca API call
        ...

# Chase adapter
class ChaseFileProvider:  # File-based
    async def fetch_accounts(self, credentials):
        file_content = credentials["file_content"]
        # Parse QFX/CSV file
        ...
```

**All three adapters satisfy the same protocol** — application code doesn't know which provider is used!

---

## Benefits

### 1. Flexibility

**Easy to swap implementations**:

```python
# Development: In-memory cache
cache: CacheProtocol = InMemoryCache()

# Production: Redis cache
cache: CacheProtocol = RedisCache()

# Testing: Mock cache
cache: CacheProtocol = AsyncMock(spec=CacheProtocol)
```

**Same interface, different implementations** — no code changes needed.

### 2. Testability

**Mock without inheritance**:

```python
# NO inheritance required for mock
mock_repo = AsyncMock(spec=UserRepository)

handler = RegisterUserHandler(user_repo=mock_repo)
```

**Fast unit tests** — no database, no framework.

### 3. Type Safety

**mypy verifies protocol compatibility**:

```python
def process(repo: UserRepository):
    ...

# mypy checks
process(PostgresUserRepository(...))  # ✅ OK
process(MongoUserRepository(...))     # ✅ OK
process(SomeRandomClass(...))          # ❌ mypy error!
```

### 4. Pythonic

**Aligns with Python philosophy**:

- Duck typing (if it walks like a duck...)
- No forced inheritance
- Structural typing
- EAFP (Easier to Ask Forgiveness than Permission)

### 5. Framework Independence

**Third-party code can satisfy protocols**:

```python
class Logger(Protocol):
    def log(self, message: str) -> None: ...

# Standard library logger satisfies protocol!
import logging
logger = logging.getLogger()  # Works!
```

---

## Comparison: Protocol vs ABC

### Side-by-Side

| Aspect | ABC (Nominal) | Protocol (Structural) |
|--------|---------------|----------------------|
| **Type Checking** | Inheritance-based | Shape-based |
| **Inheritance Required** | Yes | No |
| **Third-Party Adaptation** | Hard (wrapper needed) | Easy (duck typing) |
| **Testing** | Mock must inherit | Mock doesn't inherit |
| **Pythonic** | Less Pythonic | More Pythonic |
| **Runtime Overhead** | Minimal | None |
| **Framework Independence** | Tight coupling | Loose coupling |

### When ABC is Appropriate

**ABC is fine for**:

- Python standard library (already uses ABC)
- When you control all implementations
- When inheritance is semantically correct

**But Protocol is preferred in Dashtam** for flexibility and testability.

---

## References

**Related Architecture Documents**:

- [Hexagonal Architecture](hexagonal.md) - Protocols as ports
- [Domain-Driven Design](domain-driven-design.md) - Repository protocols
- [CQRS Pattern](cqrs.md) - Handler dependencies
- [Directory Structure](directory-structure.md) - Protocol consolidation
- [Dependency Injection](dependency-injection.md) - Protocol-based DI

**External Resources**:

- [PEP 544 – Protocols](https://peps.python.org/pep-0544/)
- [mypy Protocols](https://mypy.readthedocs.io/en/stable/protocols.html)
- [Python Type Checking Guide](https://realpython.com/python-type-checking/)

---

**Created**: 2025-12-30 | **Last Updated**: 2026-01-10
