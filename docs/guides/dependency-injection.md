# Dependency Injection Usage Guide

Practical patterns for working with the Dashtam DI system.

**Related**: `docs/architecture/dependency-injection.md` (detailed design)

---

## 1. Quick Start

### Getting Dependencies in Routers (FastAPI)

```python
from fastapi import APIRouter, Depends

from src.application.commands.handlers.register_user_handler import RegisterUserHandler
from src.core.container.handler_factory import handler_factory

router = APIRouter()

@router.post("/users", status_code=201)
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(handler_factory(RegisterUserHandler)),
) -> UserResponse:
    """Handler auto-wired with all dependencies via handler_factory."""
    result = await handler.handle(RegisterUser(email=data.email, ...))
    # ... handle result
```

**Note**: `handler_factory(HandlerClass)` automatically resolves all handler dependencies
(repositories, singletons, etc.) based on constructor type hints.

### Getting Dependencies in Application Layer

```python
from src.core.container import get_cache, get_logger

# Direct use (application layer code)
cache = get_cache()
logger = get_logger()

await cache.set("key", "value", ttl=300)
logger.info("operation_completed", key="key")
```

---

## 2. Adding a New Dependency

### Step 1: Define the Protocol (if new interface)

```python
# src/domain/protocols/notification_protocol.py
from typing import Protocol

class NotificationProtocol(Protocol):
    """Send notifications to users."""
    
    async def send(self, user_id: str, message: str) -> None: ...
    async def send_bulk(self, user_ids: list[str], message: str) -> None: ...
```

### Step 2: Create the Implementation

```python
# src/infrastructure/notifications/email_notification.py
class EmailNotification:
    """Email-based notification adapter."""
    
    def __init__(self, smtp_client: SMTPClient) -> None:
        self._smtp = smtp_client
    
    async def send(self, user_id: str, message: str) -> None:
        # Implementation
        ...
```

### Step 3: Add Factory to Container

```python
# src/core/container/infrastructure.py
from functools import lru_cache

@lru_cache()  # Singleton - use for app-scoped dependencies
def get_notification() -> "NotificationProtocol":
    """Get notification service singleton."""
    from src.infrastructure.notifications.email_notification import EmailNotification
    
    smtp_client = SMTPClient(settings.smtp_url)
    return EmailNotification(smtp_client=smtp_client)
```

### Step 4: Export from Container

```python
# src/core/container/__init__.py
from src.core.container.infrastructure import (
    get_cache,
    get_notification,  # Add export
    ...
)

__all__ = [
    "get_cache",
    "get_notification",  # Add to __all__
    ...
]
```

---

## 3. Handler Factory (Auto-Wired DI)

Handlers use **constructor injection** - they receive dependencies via `__init__`, not by calling container functions.

### Pattern: Handler with Dependencies

```python
# src/application/commands/handlers/send_notification_handler.py
from src.domain.protocols.notification_protocol import NotificationProtocol
from src.domain.protocols.user_repository import UserRepository

class SendNotificationHandler:
    """Handler depends on protocols, not implementations."""
    
    def __init__(
        self,
        users: UserRepository,
        notifications: NotificationProtocol,
    ) -> None:
        self._users = users
        self._notifications = notifications
    
    async def handle(self, cmd: SendNotification) -> Result[None, str]:
        user = await self._users.find_by_id(cmd.user_id)
        if not user:
            return Failure(error="User not found")
        
        await self._notifications.send(str(user.id), cmd.message)
        return Success(value=None)
```

### Pattern: Auto-Wired handler_factory (Recommended)

All CQRS handlers use `handler_factory()` for automatic dependency resolution:

```python
# In router - handler_factory introspects __init__ and resolves all dependencies
from src.core.container.handler_factory import handler_factory

@router.post("/notifications")
async def send_notification(
    handler: SendNotificationHandler = Depends(handler_factory(SendNotificationHandler)),
):
    result = await handler.handle(command)
    # ...
```

`handler_factory` analyzes the handler's constructor type hints and automatically:

- Creates repository instances with the request database session
- Retrieves singletons (event bus, cache, encryption, etc.) from container
- Supports all 38 CQRS handlers without manual factory functions

**Key principle**:

---

## 4. Testing with DI

### Unit Tests: Direct Injection (No Patching)

```python
# tests/unit/test_application_send_notification_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.commands.handlers.send_notification_handler import (
    SendNotificationHandler,
)
from src.application.commands.send_notification import SendNotification

@pytest.mark.unit
class TestSendNotificationHandler:
    
    @pytest.fixture
    def mock_users(self):
        """Mock UserRepository."""
        return MagicMock()
    
    @pytest.fixture
    def mock_notifications(self):
        """Mock NotificationProtocol."""
        mock = MagicMock()
        mock.send = AsyncMock()
        return mock
    
    @pytest.fixture
    def handler(self, mock_users, mock_notifications):
        """Create handler with mocked dependencies."""
        return SendNotificationHandler(
            users=mock_users,
            notifications=mock_notifications,
        )
    
    async def test_sends_notification_to_existing_user(
        self, handler, mock_users, mock_notifications
    ):
        """Test successful notification."""
        # Arrange
        user = MagicMock(id=uuid4())
        mock_users.find_by_id = AsyncMock(return_value=user)
        
        cmd = SendNotification(user_id=user.id, message="Hello")
        
        # Act
        result = await handler.handle(cmd)
        
        # Assert
        assert isinstance(result, Success)
        mock_notifications.send.assert_called_once_with(str(user.id), "Hello")
```

### API Tests: Override Dependencies with handler_factory

```python
# tests/api/test_notification_endpoints.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.application.commands.handlers.send_notification_handler import (
    SendNotificationHandler,
)
from src.core.container.handler_factory import handler_factory
from src.main import app

@pytest.mark.api
class TestNotificationEndpoints:
    
    @pytest.fixture
    def mock_handler(self):
        """Mock handler for API tests."""
        handler = MagicMock()
        handler.handle = AsyncMock(return_value=Success(value=None))
        return handler
    
    @pytest.fixture
    def client(self, mock_handler):
        """Test client with overridden dependencies."""
        # Use handler_factory(HandlerClass) as the override key
        factory_key = handler_factory(SendNotificationHandler)
        app.dependency_overrides[factory_key] = lambda: mock_handler
        yield TestClient(app)
        app.dependency_overrides.clear()
    
    def test_send_notification_returns_200(self, client, mock_handler):
        """Test endpoint calls handler."""
        response = client.post(
            "/api/v1/notifications",
            json={"user_id": "...", "message": "Hello"},
        )
        
        assert response.status_code == 200
        mock_handler.handle.assert_called_once()
```

**Note**: The key for `dependency_overrides` must be `handler_factory(HandlerClass)` - the same
callable used in the router's `Depends()`. This ensures the mock is used instead of the real handler.

### Integration Tests: Real Dependencies

```python
# tests/integration/test_notification_database.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.user_repository import UserRepository

@pytest.mark.integration
class TestUserRepositoryIntegration:
    
    async def test_find_by_id_returns_user(self, db_session: AsyncSession):
        """Test with real database session."""
        # Create repository with real session (no mocks)
        repo = UserRepository(session=db_session)
        
        # ... test real database operations
```

---

## 5. Common Patterns

### App-Scoped vs Request-Scoped

| Scope | Decorator | Use Case | Example |
|-------|-----------|----------|---------|
| App-scoped | `@lru_cache()` | Shared resources, connection pools | `get_cache()`, `get_database()` |
| Request-scoped | `yield` generator | Per-request state, transactions | `get_db_session()` |

```python
# App-scoped: Same instance for entire app lifetime
@lru_cache()
def get_cache() -> CacheProtocol:
    return RedisAdapter(...)  # Created once, reused

# Request-scoped: New instance per request
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_database().session() as session:
        yield session  # New session per request
```

### Backend Selection Pattern

```python
@lru_cache()
def get_secrets() -> SecretsProtocol:
    """Select backend based on environment."""
    import os
    
    backend = os.getenv("SECRETS_BACKEND", "env")
    
    if backend == "aws":
        from src.infrastructure.secrets.aws_adapter import AWSAdapter
        return AWSAdapter(...)
    elif backend == "env":
        from src.infrastructure.secrets.env_adapter import EnvAdapter
        return EnvAdapter()
    else:
        raise ValueError(f"Unsupported backend: {backend}")
```

### Clearing Cache for Tests

```python
def test_with_fresh_cache():
    """Clear singleton cache before test."""
    from src.core.container import get_cache
    
    get_cache.cache_clear()  # Force new instance
    
    # Now test with fresh dependency
    cache = get_cache()
```

---

## 6. Troubleshooting

### Circular Import Errors

**Symptom**: `ImportError: cannot import name 'X' from partially initialized module`

**Solution**: Use local imports inside factory functions:

```python
# ❌ Wrong: Top-level import causes circular dependency
from src.infrastructure.cache.redis_adapter import RedisAdapter

@lru_cache()
def get_cache():
    return RedisAdapter(...)

# ✅ Correct: Local import inside function
@lru_cache()
def get_cache():
    from src.infrastructure.cache.redis_adapter import RedisAdapter
    return RedisAdapter(...)
```

### Stale Cached Dependencies

**Symptom**: Tests interfere with each other, old state persists

**Solution**: Clear cache in test fixtures:

```python
@pytest.fixture(autouse=True)
def clear_container_caches():
    """Clear all container caches before each test."""
    from src.core.container import get_cache, get_logger, get_secrets
    
    get_cache.cache_clear()
    get_logger.cache_clear()
    get_secrets.cache_clear()
    
    yield
```

### Type Errors with Protocol Returns

**Symptom**: `Argument of type "X" cannot be assigned to parameter of type "Protocol"`

**Solution**: Container returns protocol type, implementation satisfies it structurally:

```python
# Container returns protocol type (not implementation)
def get_cache() -> CacheProtocol:
    return RedisAdapter(...)  # RedisAdapter satisfies CacheProtocol

# Handler depends on protocol
class MyHandler:
    def __init__(self, cache: CacheProtocol):  # Not RedisAdapter
        self._cache = cache
```

### "Event loop is closed" in Tests

**Symptom**: `RuntimeError: Event loop is closed` during async tests

**Solution**: Ensure session is passed through, not created inside handlers:

```python
# ❌ Wrong: Creating session inside handler
class MyHandler:
    async def handle(self, cmd):
        async with get_database().session() as session:  # Creates new loop
            ...

# ✅ Correct: Session injected from outside
class MyHandler:
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def handle(self, cmd):
        # Use injected session
        ...
```

---

## 7. Container Module Reference

| Module | Contents |
|--------|----------|
| `infrastructure.py` | `get_cache`, `get_secrets`, `get_database`, `get_db_session`, `get_logger`, `get_encryption_service`, `get_password_service`, `get_token_service`, `get_email_service`, `get_rate_limit`, `get_audit` |
| `events.py` | `get_event_bus` (with registry-driven handler subscriptions) |
| `repositories.py` | `get_user_repository`, `get_provider_connection_repository`, `get_provider_repository`, `get_account_repository`, `get_transaction_repository` |
| `auth_handlers.py` | `get_register_user_handler`, `get_authenticate_user_handler`, `get_generate_auth_tokens_handler`, `get_create_session_handler`, `get_logout_user_handler`, `get_refresh_token_handler`, `get_verify_email_handler`, etc. |
| `provider_handlers.py` | `get_connect_provider_handler`, `get_disconnect_provider_handler`, `get_refresh_provider_tokens_handler`, `get_get_provider_connection_handler`, `get_list_provider_connections_handler` |
| `data_handlers.py` | `get_sync_accounts_handler`, `get_sync_holdings_handler`, `get_sync_transactions_handler`, `get_import_from_file_handler`, account/transaction query handlers |
| `providers.py` | `get_provider`, `is_oauth_provider` |
| `authorization.py` | `init_enforcer`, `get_enforcer`, `get_authorization` |

---

**Created**: 2025-12-04 | **Last Updated**: 2026-01-10
