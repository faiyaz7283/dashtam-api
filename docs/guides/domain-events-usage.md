# Domain Events Usage Guide

Complete guide for using domain events in Dashtam, including when to use them, how to define and publish events, and common anti-patterns to avoid.

## When to Use Domain Events

**Pragmatic DDD Approach**: Use domain events **only for critical workflows** that have side effects requiring coordination across multiple systems.

### ✅ Use Domain Events For

**Critical workflows with multiple side effects**:

- **User Registration** → Send welcome email + Create audit trail + Initialize user settings
- **Password Change** → Revoke all sessions + Send notification email + Audit security event
- **Provider Connection** → Fetch initial data + Create audit trail + Send confirmation
- **Token Refresh Failure** → Alert user + Audit failure + Mark provider for re-auth

**Characteristics of event-worthy workflows**:

1. **Multiple handlers** need to react to the same event
2. **Side effects are independent** (email doesn't depend on audit)
3. **Fail-open acceptable** (email failure shouldn't break registration)
4. **Eventual consistency** is acceptable (audit may lag by milliseconds)

### ❌ Don't Use Domain Events For

**Simple operations without side effects**:

- **Read operations** (view account, view transactions) → No side effects
- **Single-step CRUD** (update user profile) → Direct database call sufficient
- **Synchronous validation** (check email exists) → Use direct method call
- **Immediate response required** (calculate balance) → Not async-friendly

**Rule of thumb**: If you can't think of 2+ independent handlers, don't use events.

## Event Naming Conventions

**CRITICAL**: All events must use **past tense** (what happened, not what will happen).

### ✅ Correct Naming

```python
# Good: Past tense, describes what happened
UserRegistrationSucceeded
UserPasswordChangeSucceeded
ProviderConnectionFailed
TokenRefreshAttempted
```

### ❌ Incorrect Naming

```python
# Bad: Imperative/present tense
RegisterUser          # Command, not event
UserRegistering       # Present progressive
ChangePassword        # Imperative
ConnectProvider       # Command
```

### Naming Pattern

**Format**: `{Entity}{Action}{Outcome}`

- **Entity**: What the event is about (User, Provider, Token)
- **Action**: What happened (Registration, PasswordChange, Connection)
- **Outcome**: Result state (Attempted, Succeeded, Failed)

**Examples**:

- `UserRegistrationAttempted` - User attempted to register
- `UserRegistrationSucceeded` - User successfully registered
- `UserRegistrationFailed` - User registration failed

## Defining New Events

### Step 1: Create Event Dataclass

Events are **frozen dataclasses** inheriting from `DomainEvent`.

```python
from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent

@dataclass(frozen=True, kw_only=True)
class AccountCreated(DomainEvent):
    """Account was successfully created for a provider.
    
    Published after account data is persisted to database.
    
    Args:
        user_id: UUID of user who owns the account.
        provider_id: UUID of provider this account belongs to.
        account_id: UUID of created account.
        account_type: Type of account (checking, savings, investment).
        balance: Current account balance (for display).
    
    Handlers:
        - LoggingEventHandler: Logs account creation
        - AuditEventHandler: Creates audit record
        - NotificationEventHandler: Sends new account notification
    
    Example:
        >>> event = AccountCreated(
        ...     user_id=user_id,
        ...     provider_id=provider_id,
        ...     account_id=account_id,
        ...     account_type="checking",
        ...     balance=1000.00
        ... )
        >>> await event_bus.publish(event)
    """
    user_id: UUID
    provider_id: UUID
    account_id: UUID
    account_type: str
    balance: float
```

**Key points**:

- `frozen=True` - Events are immutable (cannot be modified after creation)
- `kw_only=True` - Forces keyword arguments (prevents positional arg errors)
- Inherit from `DomainEvent` - Auto-generates `event_id` and `occurred_at`
- Comprehensive docstring - Document handlers and usage

### Step 2: Add to Events Module

Add new event to `src/domain/events/authentication_events.py` (or create new module):

```python
# src/domain/events/account_events.py
"""Account-related domain events."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent

@dataclass(frozen=True, kw_only=True)
class AccountCreated(DomainEvent):
    # ... (event definition)

@dataclass(frozen=True, kw_only=True)
class AccountUpdated(DomainEvent):
    # ... (event definition)

@dataclass(frozen=True, kw_only=True)
class AccountClosed(DomainEvent):
    # ... (event definition)
```

### Step 3: Export from `__init__.py`

```python
# src/domain/events/__init__.py
from src.domain.events.account_events import (
    AccountCreated,
    AccountUpdated,
    AccountClosed,
)
from src.domain.events.auth_events import (
    UserRegistrationSucceeded,
    # ... other events
)

__all__ = [
    "AccountCreated",
    "AccountUpdated",
    "AccountClosed",
    "UserRegistrationSucceeded",
    # ... other events
]
```

## Publishing Events

### Session Requirement (CRITICAL)

**As of F0.9.3**: Events triggering `AuditEventHandler` **require** an explicit database session.

```python
# ✅ CORRECT - Pass session to event_bus.publish()
await event_bus.publish(
    UserRegistrationSucceeded(user_id=user.id, email=user.email),
    session=session,  # Required for audit events
)

# ❌ WRONG - Missing session parameter
await event_bus.publish(UserRegistrationSucceeded(...))
# RuntimeError: AuditEventHandler requires a database session
```

**Quick fix**: Add `session=session` parameter to all `event_bus.publish()` calls for audit events.

**Which events?** All authentication, provider, and state-change events (check if `AuditEventHandler` is subscribed).

### From Command Handlers (Application Layer)

**Recommended pattern**: Publish events from command handlers after business logic succeeds.

```python
from src.core.container import get_event_bus
from src.domain.events.auth_events import UserRegistrationSucceeded

class RegisterUserHandler:
    """Command handler for user registration."""
    
    def __init__(
        self,
        user_repo: UserRepository,
        event_bus: EventBusProtocol,
        database: DatabaseProtocol,
    ):
        self._users = user_repo
        self._event_bus = event_bus
        self._database = database
    
    async def handle(self, cmd: RegisterUser) -> Result[UUID, Error]:
        """Register new user and publish event."""
        async with self._database.get_session() as session:
            # 1. Business logic
            user = User.create(email=cmd.email, password=cmd.password)
            
            # 2. Persist to database
            await self._users.save(user)
            
            # 3. Publish event AFTER successful save WITH session
            await self._event_bus.publish(
                UserRegistrationSucceeded(
                    user_id=user.id,
                    email=user.email
                ),
                session=session,  # Required for audit
            )
            
            return Success(user.id)
```

**Key points**:

- Publish **AFTER** database commit (don't publish if save fails)
- Use dependency injection for event bus
- Events are fire-and-forget (don't await handler results)

### From Domain Services

```python
class PasswordResetService:
    """Domain service for password reset workflow."""
    
    def __init__(
        self,
        user_repo: UserRepository,
        event_bus: EventBusProtocol,
        database: DatabaseProtocol,
    ):
        self._users = user_repo
        self._event_bus = event_bus
        self._database = database
    
    async def reset_password(
        self,
        user_id: UUID,
        new_password: str,
    ) -> Result[None, Error]:
        """Reset user password and publish event."""
        async with self._database.get_session() as session:
            # 1. Fetch user
            user = await self._users.find_by_id(user_id)
            if not user:
                return Failure(UserNotFound())
            
            # 2. Change password (domain logic)
            user.change_password(new_password)
            
            # 3. Persist
            await self._users.save(user)
            
            # 4. Publish event WITH session
            await self._event_bus.publish(
                UserPasswordChangeSucceeded(
                    user_id=user.id,
                    initiated_by="admin"
                ),
                session=session,  # Required for audit
            )
            
            return Success(None)
```

## Creating Event Handlers

Event handlers react to events and perform side effects (logging, audit, email, etc.).

### Step 1: Create Handler Class

```python
# src/infrastructure/events/handlers/notification_event_handler.py
"""Notification event handler for user notifications."""

from src.domain.events.account_events import AccountCreated
from src.domain.protocols.logger_protocol import LoggerProtocol

class NotificationEventHandler:
    """Sends user notifications for account events.
    
    STUB IMPLEMENTATION: Currently logs notifications.
    Future: Integrate with notification service (push, SMS, email).
    
    Attributes:
        _logger: Logger for structured logging.
    """
    
    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize handler with logger.
        
        Args:
            logger: Logger protocol for structured logging.
        """
        self._logger = logger
    
    async def handle_account_created(self, event: AccountCreated) -> None:
        """Send notification after account creation.
        
        Args:
            event: AccountCreated event with account details.
        """
        self._logger.info(
            "notification_would_be_sent",
            notification_type="account_created",
            user_id=str(event.user_id),
            account_id=str(event.account_id),
            account_type=event.account_type,
            message=f"Your {event.account_type} account has been created!",
            # Future: Send actual push notification
        )
```

### Step 2: Wire Handler in Container

```python
# src/core/container.py
from src.infrastructure.events.handlers.notification_event_handler import NotificationEventHandler

@lru_cache()
def get_event_bus() -> InMemoryEventBus:
    """Get event bus with all handlers subscribed."""
    event_bus = InMemoryEventBus(logger=get_logger())
    
    # ... existing handlers ...
    
    # Notification handler (stub)
    notification_handler = NotificationEventHandler(logger=get_logger())
    event_bus.subscribe(AccountCreated, notification_handler.handle_account_created)
    
    return event_bus
```

### Handler Best Practices

**✅ DO**:

- Keep handlers **focused** (single responsibility)
- Handlers should be **idempotent** (safe to call multiple times)
- Use **fail-open** design (don't crash event bus)
- Log handler **errors** for debugging
- Make handlers **async** (non-blocking)

**❌ DON'T**:

- Don't call other handlers directly (use events)
- Don't depend on handler execution order (concurrent)
- Don't throw unhandled exceptions (caught by event bus)
- Don't perform long-running synchronous operations

## Integration with Audit and Logging

### Automatic Audit Trail

All events with **AuditEventHandler** subscribed are automatically audited:

```python
# Event published
await event_bus.publish(
    UserPasswordChangeSucceeded(
        user_id=user_id,
        initiated_by="user"
    )
)

# Audit handler automatically creates record:
# - action: USER_PASSWORD_CHANGED
# - user_id: <user_id>
# - resource_type: "user"
# - context: {"initiated_by": "user", "method": "self_service"}
# - timestamp: <now>
```

### Automatic Structured Logging

All events with **LoggingEventHandler** subscribed are automatically logged:

```python
# Event published
await event_bus.publish(
    ProviderConnectionSucceeded(
        user_id=user_id,
        provider_id=provider_id,
        provider_name="schwab"
    )
)

# Logging handler automatically logs (JSON):
# {
#   "event": "provider_connection_succeeded",
#   "level": "info",
#   "user_id": "<user_id>",
#   "provider_id": "<provider_id>",
#   "provider_name": "schwab",
#   "timestamp": "2025-11-18T15:00:00Z"
# }
```

## Testing Event-Driven Code

### Unit Testing Event Publication

```python
# tests/unit/test_register_user_handler.py
from unittest.mock import AsyncMock
import pytest

from src.application.commands.register_user import RegisterUserHandler
from src.domain.events.auth_events import UserRegistrationSucceeded

@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_user_publishes_event():
    """Test RegisterUserHandler publishes UserRegistrationSucceeded."""
    # Arrange
    mock_user_repo = AsyncMock()
    mock_event_bus = AsyncMock()
    
    handler = RegisterUserHandler(
        user_repo=mock_user_repo,
        event_bus=mock_event_bus
    )
    
    # Act
    result = await handler.handle(RegisterUser(
        email="test@example.com",
        password="password123"
    ))
    
    # Assert
    assert result.is_success()
    mock_event_bus.publish.assert_called_once()
    
    # Verify event type
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, UserRegistrationSucceeded)
    assert event.email == "test@example.com"
```

### Integration Testing Event Flow

```python
# tests/integration/test_user_registration_flow.py
import pytest
from src.core.container import get_event_bus

@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_registration_creates_audit_record(test_database):
    """Test UserRegistrationSucceeded creates audit record."""
    # Arrange
    event_bus = get_event_bus()
    
    # Act
    await event_bus.publish(
        UserRegistrationSucceeded(
            user_id=uuid7(),
            email="test@example.com"
        )
    )
    
    # Assert - Check audit record created
    async with test_database.get_session() as session:
        stmt = select(AuditLogModel).where(
            AuditLogModel.action == AuditAction.USER_REGISTERED
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        assert len(logs) >= 1  # At least one audit record
```

## Troubleshooting

### Handler Not Executing

**Problem**: Event published but handler doesn't execute.

**Solutions**:

1. **Check subscription**: Verify handler subscribed in `get_event_bus()`

    ```python
    # src/core/container.py
    event_bus.subscribe(MyEvent, handler.handle_my_event)
    ```

2. **Check event type**: Verify exact event type matches (case-sensitive)

    ```python
    # Wrong: Event type mismatch
    event_bus.subscribe(UserRegistered, handler.handle)  # ❌
    
    # Correct: Exact type match
    event_bus.subscribe(UserRegistrationSucceeded, handler.handle)  # ✅
    ```

3. **Check handler signature**: Must be async, accept event parameter

    ```python
    # Wrong: Missing async
    def handle_event(self, event: MyEvent):  # ❌
    
    # Correct: Async handler
    async def handle_event(self, event: MyEvent):  # ✅
    ```

### Handler Failure Breaking Event Bus

**Problem**: One handler crashes and event bus stops processing.

**Solution**: Event bus uses **fail-open** design. Handler failures are logged but don't break other handlers.

**Check logs** for handler failures:

```json
{
  "event": "event_handler_failed",
  "level": "warning",
  "event_type": "UserRegistrationSucceeded",
  "handler_name": "handle_user_registration_succeeded",
  "error_type": "ValueError",
  "error_message": "Invalid email format"
}
```

### Audit Records Not Created (Integration Tests)

**Known Issue**: Audit handler may fail in integration tests with "Event loop is closed".

**Cause**: Audit handler creates new database sessions inside event handlers, causing timing issues during test cleanup.

**Workaround**: Accept as test artifact (production not affected). See roadmap item **F0.9.2: Audit Handler Session Lifecycle Fix**.

**Verification**: Check logs for `PendingRollbackError`:

```json
{
  "event": "event_handler_failed",
  "error_type": "PendingRollbackError",
  "error_message": "Event loop is closed"
}
```

## Anti-Patterns

### ❌ Anti-Pattern 1: Events for Everything

**Bad**:

```python
# Don't create events for simple CRUD operations
await event_bus.publish(UserProfileViewed(user_id=user_id))
await event_bus.publish(AccountBalanceFetched(account_id=account_id))
await event_bus.publish(TransactionListed(user_id=user_id))
```

**Why**: Events add complexity. Use only when you need multiple handlers or decoupling.

**Good**:

```python
# Simple operations don't need events
balance = await account_repo.get_balance(account_id)
transactions = await transaction_repo.list(user_id)
```

### ❌ Anti-Pattern 2: Synchronous Handler Dependencies

**Bad**:

```python
async def handle_user_registered(self, event: UserRegistrationSucceeded):
    # ❌ Waiting for email to send before audit
    await self.send_welcome_email(event.email)
    await self.create_audit_record(event.user_id)
```

**Why**: Handlers should be independent. Email failure blocks audit.

**Good**:

```python
# ✅ Each handler operates independently
async def handle_user_registered(self, event: UserRegistrationSucceeded):
    await self.send_welcome_email(event.email)  # Separate handler

async def handle_user_registered_audit(self, event: UserRegistrationSucceeded):
    await self.create_audit_record(event.user_id)  # Separate handler
```

### ❌ Anti-Pattern 3: Imperative Event Names

**Bad**:

```python
@dataclass(frozen=True, kw_only=True)
class SendWelcomeEmail(DomainEvent):  # ❌ Command, not event
    email: str

@dataclass(frozen=True, kw_only=True)
class CreateAuditLog(DomainEvent):  # ❌ Command, not event
    action: str
```

**Why**: Events describe what **happened**, not what **should happen**.

**Good**:

```python
@dataclass(frozen=True, kw_only=True)
class UserRegistrationSucceeded(DomainEvent):  # ✅ Past tense
    user_id: UUID
    email: str
```

### ❌ Anti-Pattern 4: Mutable Events

**Bad**:

```python
@dataclass(kw_only=True)  # ❌ Missing frozen=True
class UserRegistered(DomainEvent):
    user_id: UUID
    email: str

# Event can be modified (bad!)
event.email = "changed@example.com"
```

**Why**: Events are historical facts and should never change.

**Good**:

```python
@dataclass(frozen=True, kw_only=True)  # ✅ Immutable
class UserRegistrationSucceeded(DomainEvent):
    user_id: UUID
    email: str

# Attempting to modify raises error
event.email = "changed@example.com"  # FrozenInstanceError
```

### ❌ Anti-Pattern 5: Publishing Before Commit

**Bad**:

```python
async def register_user(self, email: str) -> Result[UUID, Error]:
    user = User.create(email=email)
    
    # ❌ Publishing before database commit
    await self._event_bus.publish(UserRegistrationSucceeded(
        user_id=user.id,
        email=user.email
    ))
    
    await self._users.save(user)  # What if this fails?
    return Success(user.id)
```

**Why**: If save fails, handlers already executed (email sent, audit created) for non-existent user.

**Good**:

```python
async def register_user(self, email: str) -> Result[UUID, Error]:
    user = User.create(email=email)
    
    # ✅ Save first
    await self._users.save(user)
    
    # ✅ Publish after successful save
    await self._event_bus.publish(UserRegistrationSucceeded(
        user_id=user.id,
        email=user.email
    ))
    
    return Success(user.id)
```

## Summary

**Key Takeaways**:

1. ✅ Use events **only for critical workflows** with multiple side effects
2. ✅ Name events in **past tense** (what happened)
3. ✅ Make events **immutable** (frozen dataclasses)
4. ✅ Publish events **after database commit**
5. ✅ Keep handlers **independent** (no dependencies between handlers)
6. ✅ Test events with **unit tests** (mocks) and **integration tests** (real DB)
7. ✅ Use **fail-open** design (handler failures don't break event bus)

**Next Steps**:

- Review [Domain Events Architecture](../architecture/domain-events-architecture.md) for technical details
- Check existing events in `src/domain/events/` for examples
- See `~/starter/development-checklist.md` Section 23b for verification steps (project file)

---

**Created**: 2025-11-18 | **Last Updated**: 2025-11-18
