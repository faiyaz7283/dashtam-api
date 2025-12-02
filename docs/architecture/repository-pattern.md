# Repository Pattern Architecture

## Overview

This document establishes the repository pattern architecture for Dashtam. The
repository pattern provides a collection-like interface for accessing domain
entities while encapsulating the complexity of data storage and retrieval.

**Purpose**: Define consistent patterns for all repository implementations
across Phase 3 (ProviderConnection, Account, Transaction) and future entities.

**Scope**: Domain protocols, infrastructure implementations, entity↔model
mapping, session management, migration patterns, and query conventions.

---

## 1. Hexagonal Architecture Context

### 1.1 Ports and Adapters

The repository pattern follows hexagonal architecture principles:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         DOMAIN LAYER                                    │
│  ┌─────────────────┐     ┌─────────────────────────────────────────┐    │
│  │  Domain Entity  │     │    Repository Protocol (PORT)           │    │
│  │  - User         │◄────│    - UserRepository                     │    │
│  │  - Account      │     │    - AccountRepository                  │    │
│  │  - Transaction  │     │    - TransactionRepository              │    │
│  └─────────────────┘     └────────────────────┬────────────────────┘    │
│                                               │                         │
│        Domain depends on NOTHING              │                         │
└───────────────────────────────────────────────┼─────────────────────────┘
                                                │ implements
┌───────────────────────────────────────────────┼─────────────────────────┐
│                    INFRASTRUCTURE LAYER       ▼                         │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │    Repository Implementation (ADAPTER)                         │     │
│  │    - PostgresUserRepository                                    │     │
│  │    - PostgresAccountRepository                                 │     │
│  │    - PostgresTransactionRepository                             │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                │                                        │
│                                │ uses                                   │
│                                ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │    Database Models (SQLAlchemy)                                │     │
│  │    - UserModel                                                 │     │
│  │    - AccountModel                                              │     │
│  │    - TransactionModel                                          │     │
│  └────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Dependency Direction

- **Domain Layer**: Defines protocols (what it needs) - depends on NOTHING
- **Infrastructure Layer**: Implements protocols (how to do it) - depends on Domain
- **Application Layer**: Uses protocols via DI - depends on Domain only

**Critical Rule**: Domain entities NEVER import infrastructure models.
Infrastructure models map TO/FROM domain entities.

---

## 2. Protocol Definition (Domain Layer)

### 2.1 Location and Naming

All repository protocols reside in `src/domain/protocols/`:

```text
src/domain/protocols/
├── __init__.py                          # Exports all protocols
├── user_repository.py                   # UserRepository protocol
├── provider_connection_repository.py    # ProviderConnectionRepository protocol
├── account_repository.py                # AccountRepository protocol
└── transaction_repository.py            # TransactionRepository protocol
```

**Naming Convention**: `{Entity}Repository` (e.g., `AccountRepository`)

### 2.2 Protocol Structure

```python
# src/domain/protocols/account_repository.py
"""AccountRepository protocol for account persistence.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol.

Reference:
    - docs/architecture/account-domain-model.md
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.account import Account


class AccountRepository(Protocol):
    """Account repository protocol (port).

    Defines the interface for account persistence operations.
    Infrastructure layer provides concrete implementation.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        find_by_id: Retrieve account by ID
        find_by_connection_id: Retrieve accounts for connection
        save: Create or update account
        delete: Remove account
    """

    async def find_by_id(self, account_id: UUID) -> Account | None:
        """Find account by ID.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Account if found, None otherwise.
        """
        ...

    async def find_by_connection_id(
        self,
        connection_id: UUID,
    ) -> list[Account]:
        """Find all accounts for a provider connection."""
        ...

    async def save(self, account: Account) -> None:
        """Create or update account in database."""
        ...

    async def delete(self, account_id: UUID) -> None:
        """Remove account from database."""
        ...
```

### 2.3 Protocol Guidelines

**DO**:

- Use `Protocol` from `typing` (NOT `ABC`)
- Define async methods with proper type hints
- Return domain entities (NOT database models)
- Use domain language in method names (`find_active_by_user`, NOT `get_users_where_active_true`)
- Include comprehensive docstrings with Args/Returns/Example
- Define `...` (ellipsis) as method body

**DON'T**:

- Import infrastructure modules
- Reference SQLAlchemy types
- Include implementation details
- Use database terminology (`SELECT`, `WHERE`, etc.)

### 2.4 Architecture Decision: Queries-Only Domain Entities

**Decision**: Domain entities in Dashtam expose only query methods (getters) and NO mutation methods (setters).

#### Rationale

**Traditional Approach** (Mutation in Entities):

```python
# ❌ DON'T: Mutation methods in entity
class Account:
    def update_balance(self, new_balance: Money) -> None:
        """Update account balance."""
        self.balance = new_balance
        self.updated_at = datetime.now(UTC)
    
    def deactivate(self) -> None:
        """Deactivate account."""
        self.is_active = False
```

**Problems with Mutation Methods**:

1. **Unclear Intent**: What business event triggered this mutation?
2. **No Audit Trail**: Can't track why balance changed
3. **Coupling**: Entity knows about database concerns (`updated_at`)
4. **Hard to Test**: Which method combinations are valid?
5. **Event Emission**: Where do domain events fit?

**Dashtam Approach** (Queries-Only):

```python
# ✅ DO: Queries-only entity
@dataclass(frozen=True)
class Account:
    """Account domain entity (immutable).
    
    This entity exposes ONLY query methods (getters).
    ALL mutations happen through CQRS command handlers.
    """
    id: UUID
    connection_id: UUID
    name: str
    balance: Money
    is_active: bool
    
    # Query methods ONLY
    def is_below_threshold(self, threshold: Money) -> bool:
        """Check if balance is below threshold."""
        return self.balance.amount < threshold.amount
    
    def can_withdraw(self, amount: Money) -> bool:
        """Check if withdrawal is possible."""
        return self.is_active and self.balance.amount >= amount.amount
    
    # NO mutation methods!
    # Use UpdateAccountBalanceHandler instead
```

#### How Mutations Work in CQRS

All state changes happen through **Command Handlers**:

```python
# Command represents user intent
@dataclass(frozen=True, kw_only=True)
class UpdateAccountBalance:
    """Update account balance command."""
    account_id: UUID
    new_balance: Money
    reason: str  # Audit trail

# Handler orchestrates the mutation
class UpdateAccountBalanceHandler:
    async def handle(self, cmd: UpdateAccountBalance) -> Result[None, str]:
        # 1. Emit ATTEMPTED event (audit)
        await self._event_bus.publish(
            AccountBalanceUpdateAttempted(
                account_id=cmd.account_id,
                reason=cmd.reason,
            )
        )
        
        # 2. Load entity (immutable)
        account = await self._accounts.find_by_id(cmd.account_id)
        
        # 3. Create NEW entity with updated values
        updated_account = dataclasses.replace(
            account,
            balance=cmd.new_balance,
            updated_at=datetime.now(UTC),
        )
        
        # 4. Save (repository handles persistence)
        await self._accounts.save(updated_account)
        
        # 5. Emit SUCCEEDED event (audit)
        await self._event_bus.publish(
            AccountBalanceUpdateSucceeded(
                account_id=cmd.account_id,
                new_balance=cmd.new_balance,
                reason=cmd.reason,
            )
        )
        
        return Success(None)
```

#### Benefits of Queries-Only Approach

| Aspect | Traditional (Mutation Methods) | Queries-Only (CQRS) |
|--------|--------------------------------|---------------------|
| **Intent** | Unclear which method to call | Explicit command name |
| **Audit** | Hard to track mutations | 3-state events automatic |
| **Testing** | Test complex method chains | Test handlers independently |
| **Events** | Where to emit events? | Built into handler pattern |
| **Validation** | Scattered across methods | Centralized in command |
| **Coupling** | Entity knows infrastructure | Entity is pure domain |
| **Immutability** | Mutable state (bugs) | Immutable entities (safe) |

#### Domain Entity Guidelines

**DO** add query methods that:

- Return boolean checks (`is_active()`, `can_withdraw()`)
- Calculate derived values (`total_value()`, `tax_amount()`)
- Format display values (`formatted_balance()`, `masked_number()`)
- Compare states (`is_newer_than()`, `matches_criteria()`)

**DON'T** add mutation methods that:

- Change entity state (`update_balance()`, `deactivate()`)
- Persist to database (`save()`, `delete()`)
- Emit domain events (`publish_updated()`)
- Handle business workflows (`process_transaction()`)

**Instead**: Create a command handler for each mutation.

#### Example: Account Entity (Queries-Only)

```python
@dataclass(frozen=True)
class Account:
    """Account domain entity.
    
    Immutable entity with query methods only.
    Mutations handled by command handlers.
    """
    id: UUID
    connection_id: UUID
    provider_account_id: str
    name: str
    account_type: AccountType
    balance: Money
    available_balance: Money | None
    is_active: bool
    last_synced_at: datetime | None
    
    # =========================================================================
    # Query Methods (Safe to Add)
    # =========================================================================
    
    def is_synced_recently(self, threshold_hours: int = 24) -> bool:
        """Check if account was synced within threshold."""
        if self.last_synced_at is None:
            return False
        age = datetime.now(UTC) - self.last_synced_at
        return age.total_seconds() < (threshold_hours * 3600)
    
    def has_available_funds(self, amount: Money) -> bool:
        """Check if sufficient available balance."""
        if not self.is_active:
            return False
        balance_to_check = self.available_balance or self.balance
        return balance_to_check.amount >= amount.amount
    
    def formatted_balance(self) -> str:
        """Format balance for display."""
        return f"{self.balance.currency} {self.balance.amount:,.2f}"
    
    # =========================================================================
    # NO Mutation Methods
    # =========================================================================
    # ❌ update_balance()       → Use UpdateAccountBalanceHandler
    # ❌ deactivate()           → Use Deactivate AccountHandler
    # ❌ mark_synced()          → Use SyncAccountHandler
```

#### Migration Guide for Existing Code

If you find mutation methods in domain entities:

1. **Identify the business intent**: What command does this represent?
2. **Create a command**: Define the command in `src/application/commands/`
3. **Create a handler**: Implement the mutation in a command handler
4. **Emit events**: Add 3-state events for audit trail
5. **Remove mutation method**: Delete from entity, make entity immutable
6. **Update callers**: Change `entity.update_X()` to `await handler.handle(UpdateX(...))`

#### References

- `docs/architecture/cqrs-pattern.md` - Command/Query separation
- `docs/architecture/domain-events-architecture.md` - Event-driven mutations
- `src/domain/entities/` - Example entities (all queries-only)
- `src/application/commands/handlers/` - Example mutation handlers

---

## 3. Repository Implementation (Infrastructure Layer)

### 3.1 Location and Naming

Repository implementations reside in `src/infrastructure/persistence/repositories/`:

```text
src/infrastructure/persistence/repositories/
├── __init__.py                              # Exports all repositories
├── user_repository.py                       # UserRepository implementation
├── provider_connection_repository.py        # ProviderConnectionRepository impl
├── account_repository.py                    # AccountRepository implementation
└── transaction_repository.py                # TransactionRepository implementation
```

**Naming Convention**: Same as protocol - `{Entity}Repository`
(structural typing - no inheritance needed)

### 3.2 Implementation Structure

```python
# src/infrastructure/persistence/repositories/account_repository.py
"""AccountRepository - SQLAlchemy implementation of AccountRepository protocol.

Adapter for hexagonal architecture.
Maps between domain Account entities and database AccountModel.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.models.account import (
    Account as AccountModel,
)


class AccountRepository:
    """SQLAlchemy implementation of AccountRepository protocol.

    This is an adapter that implements the AccountRepository port.
    It handles the mapping between domain Account entities and database AccountModel.

    This class does NOT inherit from AccountRepository protocol
    (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def find_by_id(self, account_id: UUID) -> Account | None:
        """Find account by ID.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Domain Account entity if found, None otherwise.
        """
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def save(self, account: Account) -> None:
        """Create or update account in database.

        Args:
            account: Domain Account entity to persist.
        """
        # Check if exists for upsert logic
        existing = await self.session.get(AccountModel, account.id)

        if existing:
            # Update existing model
            self._update_model(existing, account)
        else:
            # Create new model
            model = self._to_model(account)
            self.session.add(model)

        await self.session.commit()

    # =========================================================================
    # Entity ↔ Model Mapping (Private Methods)
    # =========================================================================

    def _to_domain(self, model: AccountModel) -> Account:
        """Convert database model to domain entity.

        Args:
            model: SQLAlchemy AccountModel instance.

        Returns:
            Domain Account entity.
        """
        return Account(
            id=model.id,
            connection_id=model.connection_id,
            provider_account_id=model.provider_account_id,
            account_number_masked=model.account_number_masked,
            name=model.name,
            account_type=AccountType(model.account_type),
            balance=Money(amount=model.balance, currency=model.currency),
            currency=model.currency,
            available_balance=(
                Money(amount=model.available_balance, currency=model.currency)
                if model.available_balance is not None
                else None
            ),
            is_active=model.is_active,
            last_synced_at=model.last_synced_at,
            provider_metadata=model.provider_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Account) -> AccountModel:
        """Convert domain entity to database model.

        Args:
            entity: Domain Account entity.

        Returns:
            SQLAlchemy AccountModel instance.
        """
        return AccountModel(
            id=entity.id,
            connection_id=entity.connection_id,
            provider_account_id=entity.provider_account_id,
            account_number_masked=entity.account_number_masked,
            name=entity.name,
            account_type=entity.account_type.value,
            balance=entity.balance.amount,
            currency=entity.currency,
            available_balance=(
                entity.available_balance.amount
                if entity.available_balance is not None
                else None
            ),
            is_active=entity.is_active,
            last_synced_at=entity.last_synced_at,
            provider_metadata=entity.provider_metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _update_model(self, model: AccountModel, entity: Account) -> None:
        """Update existing model from entity (for upsert).

        Args:
            model: Existing SQLAlchemy model to update.
            entity: Domain entity with new values.
        """
        model.name = entity.name
        model.balance = entity.balance.amount
        model.available_balance = (
            entity.available_balance.amount
            if entity.available_balance is not None
            else None
        )
        model.is_active = entity.is_active
        model.last_synced_at = entity.last_synced_at
        model.provider_metadata = entity.provider_metadata
        model.updated_at = datetime.now(UTC)
```

### 3.3 Implementation Guidelines

**DO**:

- Accept `AsyncSession` in constructor (dependency injection)
- Implement `_to_domain()` and `_to_model()` private mapping methods
- Handle None cases explicitly in `find_*` methods
- Use SQLAlchemy `select()` for queries
- Commit transactions in repository methods
- Use `scalar_one_or_none()` for single results
- Use `scalars().all()` for multiple results

**DON'T**:

- Inherit from the Protocol class (structural typing)
- Raise exceptions for not-found cases (return None instead)
- Expose database models to callers
- Import domain entities from infrastructure (reverse dependency)

---

## 4. Entity ↔ Model Mapping

### 4.1 Mapping Principles

Domain entities and database models are **separate concerns**:

```text
Domain Entity (dataclass)           Database Model (SQLAlchemy)
━━━━━━━━━━━━━━━━━━━━━━━━━           ━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Pure Python                       - SQLAlchemy ORM
- Business logic                    - Database schema
- Immutable or controlled           - Mutable
- Value objects                     - Primitive types
- Enums                             - Strings/Integers
```

### 4.2 Type Conversions

Common type conversions between entity and model:

| Domain Type | Database Type | Entity → Model | Model → Entity |
|-------------|---------------|----------------|----------------|
| `UUID` | `UUID` | Direct | Direct |
| `datetime` | `DateTime(timezone=True)` | Direct | Direct |
| `Enum` | `String` | `.value` | `Enum(value)` |
| `Money` | `Decimal` + `String` | `.amount`, `.currency` | `Money(amount, currency)` |
| `Decimal` | `Numeric` | Direct | Direct |
| `bool` | `Boolean` | Direct | Direct |
| `dict` | `JSONB` | Direct (JSON serializable) | Direct |
| `list` | `ARRAY` or `JSONB` | Direct | Direct |
| `ProviderCredentials` | `LargeBinary` + `String` | `.encrypted_data`, `.credential_type.value` | Constructor |

### 4.3 Value Object Mapping Example

```python
# Domain value object
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

# In repository mapping
def _to_domain(self, model: AccountModel) -> Account:
    return Account(
        # ... other fields ...
        balance=Money(amount=model.balance, currency=model.currency),
    )

def _to_model(self, entity: Account) -> AccountModel:
    return AccountModel(
        # ... other fields ...
        balance=entity.balance.amount,
        currency=entity.currency,
    )
```

### 4.4 Nullable Field Handling

```python
# Entity has optional field
available_balance: Money | None = None

# Model has nullable column
available_balance: Mapped[Decimal | None] = mapped_column(
    Numeric(precision=19, scale=4),
    nullable=True,
)

# Mapping handles None
def _to_domain(self, model: AccountModel) -> Account:
    return Account(
        available_balance=(
            Money(amount=model.available_balance, currency=model.currency)
            if model.available_balance is not None
            else None
        ),
    )
```

---

## 5. Database Models

### 5.1 Location and Naming

Database models reside in `src/infrastructure/persistence/models/`:

```text
src/infrastructure/persistence/models/
├── __init__.py                      # Exports all models
├── user.py                          # User model
├── provider_connection.py           # ProviderConnection model
├── account.py                       # Account model
└── transaction.py                   # Transaction model
```

**Naming Convention**: Same as entity name (e.g., `Account` for both)
Import alias to distinguish: `from ...models.account import Account as AccountModel`

### 5.2 Base Model Inheritance

```python
from src.infrastructure.persistence.base import BaseMutableModel, BaseModel

# Mutable entities (can be updated) - MOST COMMON
class Account(BaseMutableModel):
    """Account database model."""
    __tablename__ = "accounts"
    # Inherits: id, created_at, updated_at

# Immutable entities (cannot be updated)
class AuditLog(BaseModel):
    """Audit log database model."""
    __tablename__ = "audit_logs"
    # Inherits: id, created_at (no updated_at)
```

### 5.3 Model Structure

```python
# src/infrastructure/persistence/models/account.py
"""Account database model.

Maps to the accounts table in PostgreSQL.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class Account(BaseMutableModel):
    """Account model for financial account storage.

    Attributes:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when created (from BaseMutableModel)
        updated_at: Timestamp when last updated (from BaseMutableModel)
        connection_id: FK to provider_connections table
        provider_account_id: Provider's unique identifier
        account_number_masked: Masked account number (****1234)
        name: Account name from provider
        account_type: Type (BROKERAGE, CHECKING, etc.)
        balance: Current balance amount
        currency: ISO 4217 currency code
        available_balance: Available balance (nullable)
        is_active: Whether account is active
        last_synced_at: Last successful sync timestamp
        provider_metadata: Provider-specific data (JSONB)
    """

    __tablename__ = "accounts"

    # Foreign key to provider_connections
    connection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provider_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to provider_connections table",
    )

    # Provider's unique identifier
    provider_account_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Provider's unique account identifier",
    )

    # Masked account number for display
    account_number_masked: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Masked account number (****1234)",
    )

    # Account name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Account name from provider",
    )

    # Account type (stored as string, mapped to enum)
    account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Account type (BROKERAGE, CHECKING, etc.)",
    )

    # Balance (Decimal for precision)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        comment="Current balance amount",
    )

    # Currency code
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    # Available balance (nullable)
    available_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Available balance (if different from balance)",
    )

    # Active status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether account is active",
    )

    # Last sync timestamp
    last_synced_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last successful sync timestamp",
    )

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific data (unstructured)",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Account("
            f"id={self.id}, "
            f"name={self.name!r}, "
            f"account_type={self.account_type!r}"
            f")>"
        )
```

### 5.4 Column Type Guidelines

| Data Type | SQLAlchemy Type | Notes |
|-----------|-----------------|-------|
| UUID | `UUID` (from sqlalchemy) | Works cross-database |
| UUID (PG-specific) | `PG_UUID(as_uuid=True)` | PostgreSQL native |
| String | `String(length)` | Always specify length |
| Decimal | `Numeric(precision=19, scale=4)` | For money |
| DateTime | `DateTime(timezone=True)` | Always timezone-aware |
| Boolean | `Boolean` | Direct mapping |
| JSON | `JSONB` (PostgreSQL) | For unstructured data |
| Binary | `LargeBinary` | For encrypted credentials |
| Enum | `String` | Store as string, map in code |

---

## 6. Session Management

### 6.1 Session Lifecycle

Sessions are request-scoped and managed by the container:

```python
# src/core/container.py

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (request-scoped).

    Yields:
        AsyncSession: Database session for operations.

    Note:
        Session is committed on successful exit, rolled back on exception.
    """
    db = get_database()
    async with db.get_session() as session:
        yield session
```

### 6.2 Repository Usage in Handlers

```python
# Application layer handler
class CreateAccountHandler:
    def __init__(
        self,
        account_repo: AccountRepository,  # Injected via DI
    ) -> None:
        self._accounts = account_repo

    async def handle(self, cmd: CreateAccount) -> Result[UUID, Error]:
        account = Account(...)
        await self._accounts.save(account)  # Commits in repository
        return Success(account.id)
```

### 6.3 Transaction Boundaries

**Single Repository Operation**: Commit in repository method

```python
async def save(self, account: Account) -> None:
    model = self._to_model(account)
    self.session.add(model)
    await self.session.commit()  # ✅ Commit here
```

**Multiple Repository Operations**: Use explicit transaction

```python
# When operations must succeed/fail together
async with db.transaction() as session:
    account_repo = AccountRepository(session)
    transaction_repo = TransactionRepository(session)

    await account_repo.save(account)
    await transaction_repo.save_many(transactions)
    # Both commit together or both rollback
```

### 6.4 Commit Patterns

| Scenario | Commit Location | Pattern |
|----------|-----------------|---------|
| Single save/update | Repository method | `await session.commit()` |
| Multiple independent ops | Each repository method | Each commits separately |
| Multiple dependent ops | Caller (handler) | Use `db.transaction()` |
| Bulk operations | Repository method | Single commit after all |

---

## 7. Alembic Migrations

### 7.1 Migration Workflow

```bash
# 1. Create migration (auto-generate from model changes)
make migrate-create MSG="add accounts table"

# 2. Review generated migration in alembic/versions/

# 3. Apply migration
make migrate

# 4. (If needed) Rollback
make migrate-down
```

### 7.2 Migration Structure

```python
# alembic/versions/2025_12_01_xxxx_add_accounts_table.py
"""Add accounts table.

Revision ID: xxxxxxxxxxxx
Revises: previous_revision
Create Date: 2025-12-01 xx:xx:xx.xxxxxx
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "xxxxxxxxxxxx"
down_revision = "previous_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create accounts table."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_account_id", sa.String(100), nullable=False),
        sa.Column("account_number_masked", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False),
        sa.Column("balance", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("available_balance", sa.Numeric(19, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["provider_connections.id"],
            ondelete="CASCADE",
        ),
    )

    # Indexes
    op.create_index("ix_accounts_connection_id", "accounts", ["connection_id"])
    op.create_index("ix_accounts_account_type", "accounts", ["account_type"])
    op.create_index("ix_accounts_is_active", "accounts", ["is_active"])

    # Unique constraint: one provider_account_id per connection
    op.create_unique_constraint(
        "uq_accounts_connection_provider",
        "accounts",
        ["connection_id", "provider_account_id"],
    )


def downgrade() -> None:
    """Drop accounts table."""
    op.drop_table("accounts")
```

### 7.3 Foreign Key Conventions

| Relationship | ondelete | Notes |
|--------------|----------|-------|
| User → Session | `CASCADE` | Delete sessions when user deleted |
| Connection → Account | `CASCADE` | Delete accounts when connection deleted |
| Account → Transaction | `CASCADE` | Delete transactions when account deleted |
| Connection → User | `RESTRICT` | Prevent user deletion if connections exist |

---

## 8. Query Patterns

### 8.1 Basic Queries

```python
# Find by ID
async def find_by_id(self, account_id: UUID) -> Account | None:
    stmt = select(AccountModel).where(AccountModel.id == account_id)
    result = await self.session.execute(stmt)
    model = result.scalar_one_or_none()
    return self._to_domain(model) if model else None

# Find by foreign key
async def find_by_connection_id(self, connection_id: UUID) -> list[Account]:
    stmt = select(AccountModel).where(
        AccountModel.connection_id == connection_id
    )
    result = await self.session.execute(stmt)
    models = result.scalars().all()
    return [self._to_domain(m) for m in models]
```

### 8.2 Pagination

```python
async def find_by_account_id(
    self,
    account_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    stmt = (
        select(TransactionModel)
        .where(TransactionModel.account_id == account_id)
        .order_by(TransactionModel.transaction_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await self.session.execute(stmt)
    models = result.scalars().all()
    return [self._to_domain(m) for m in models]
```

### 8.3 Filtering

```python
async def find_active_by_user(self, user_id: UUID) -> list[Account]:
    stmt = (
        select(AccountModel)
        .join(ProviderConnectionModel)
        .where(
            ProviderConnectionModel.user_id == user_id,
            AccountModel.is_active == True,  # noqa: E712
        )
    )
    result = await self.session.execute(stmt)
    models = result.scalars().all()
    return [self._to_domain(m) for m in models]
```

### 8.4 Date Range Queries

```python
async def find_by_date_range(
    self,
    account_id: UUID,
    start_date: date,
    end_date: date,
) -> list[Transaction]:
    stmt = (
        select(TransactionModel)
        .where(
            TransactionModel.account_id == account_id,
            TransactionModel.transaction_date >= start_date,
            TransactionModel.transaction_date <= end_date,
        )
        .order_by(TransactionModel.transaction_date.asc())
    )
    result = await self.session.execute(stmt)
    models = result.scalars().all()
    return [self._to_domain(m) for m in models]
```

### 8.5 Existence Check

```python
async def exists_by_email(self, email: str) -> bool:
    stmt = select(UserModel.id).where(UserModel.email.ilike(email))
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none() is not None
```

---

## 9. Testing Strategy

### 9.1 Infrastructure Layer Testing

**Rule**: Integration tests ONLY for repository implementations.
No unit tests for infrastructure adapters.

```text
tests/integration/
├── test_user_repository.py
├── test_provider_connection_repository.py
├── test_account_repository.py
└── test_transaction_repository.py
```

### 9.2 Test Structure

```python
# tests/integration/test_account_repository.py
"""Integration tests for AccountRepository.

Tests cover:
- Save and retrieve account
- Find by connection ID
- Find by user ID (across connections)
- Update account
- Delete account
- Foreign key constraints

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from uuid_extensions import uuid7

from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)


def create_test_account(
    account_id=None,
    connection_id=None,
    **kwargs,
) -> Account:
    """Create a test Account with default values."""
    now = datetime.now(UTC)
    return Account(
        id=account_id or uuid7(),
        connection_id=connection_id or uuid7(),
        provider_account_id=kwargs.get("provider_account_id", "TEST-12345"),
        account_number_masked=kwargs.get("account_number_masked", "****1234"),
        name=kwargs.get("name", "Test Account"),
        account_type=kwargs.get("account_type", AccountType.BROKERAGE),
        balance=kwargs.get("balance", Money(Decimal("1000.00"), "USD")),
        currency=kwargs.get("currency", "USD"),
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def account_repository(test_database):
    """Provide AccountRepository with test database session."""
    async with test_database.get_session() as session:
        yield AccountRepository(session=session)


@pytest.mark.integration
class TestAccountRepositorySave:
    """Test AccountRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_account_persists_to_database(self, test_database):
        """Test saving an account persists it to the database."""
        # Arrange
        account_id = uuid7()
        account = create_test_account(account_id=account_id)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)
            await session.commit()

        # Assert - Use separate session to verify persistence
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account_id)

            assert found is not None
            assert found.id == account_id
            assert found.name == "Test Account"
```

### 9.3 Test Fixtures

```python
# tests/conftest.py

@pytest_asyncio.fixture
async def test_database():
    """Provide test database instance."""
    from src.core.config import settings
    from src.infrastructure.persistence.database import Database

    db = Database(database_url=settings.database_url)
    yield db
    await db.close()


@pytest_asyncio.fixture
async def test_user(test_database) -> User:
    """Create a test user for foreign key dependencies."""
    user = create_test_user()
    async with test_database.get_session() as session:
        repo = UserRepository(session=session)
        await repo.save(user)
        await session.commit()
    return user


@pytest_asyncio.fixture
async def test_connection(test_database, test_user) -> ProviderConnection:
    """Create a test provider connection for foreign key dependencies."""
    connection = create_test_connection(user_id=test_user.id)
    async with test_database.get_session() as session:
        repo = ProviderConnectionRepository(session=session)
        await repo.save(connection)
        await session.commit()
    return connection
```

### 9.4 Coverage Targets

| Component | Coverage Target |
|-----------|----------------|
| Repository implementations | 90%+ |
| Entity ↔ Model mapping | 100% |
| Query methods | 90%+ |
| Edge cases (nulls, not found) | 100% |

---

## 10. Container Integration

### 10.1 Repository Factory Functions

```python
# src/core/container.py

def get_provider_connection_repository(
    session: AsyncSession,
) -> ProviderConnectionRepository:
    """Get ProviderConnectionRepository instance.

    Args:
        session: Database session (request-scoped).

    Returns:
        ProviderConnectionRepository implementation.
    """
    from src.infrastructure.persistence.repositories.provider_connection_repository import (
        ProviderConnectionRepository as ProviderConnectionRepositoryImpl,
    )
    return ProviderConnectionRepositoryImpl(session=session)


def get_account_repository(session: AsyncSession) -> AccountRepository:
    """Get AccountRepository instance."""
    from src.infrastructure.persistence.repositories.account_repository import (
        AccountRepository as AccountRepositoryImpl,
    )
    return AccountRepositoryImpl(session=session)


def get_transaction_repository(session: AsyncSession) -> TransactionRepository:
    """Get TransactionRepository instance."""
    from src.infrastructure.persistence.repositories.transaction_repository import (
        TransactionRepository as TransactionRepositoryImpl,
    )
    return TransactionRepositoryImpl(session=session)
```

### 10.2 Usage in Presentation Layer

```python
# src/presentation/api/v1/accounts.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container import get_db_session, get_account_repository
from src.domain.protocols.account_repository import AccountRepository

router = APIRouter()


@router.get("/accounts")
async def list_accounts(
    session: AsyncSession = Depends(get_db_session),
    account_repo: AccountRepository = Depends(
        lambda session=Depends(get_db_session): get_account_repository(session)
    ),
):
    accounts = await account_repo.find_by_user_id(current_user.id)
    return [AccountResponse.from_entity(a) for a in accounts]
```

---

## 11. Summary: Repository Checklist

When implementing a new repository:

**Domain Layer (Protocol)**:

- [ ] Create protocol in `src/domain/protocols/{entity}_repository.py`
- [ ] Use `Protocol` from `typing` (not ABC)
- [ ] Define async methods returning domain entities
- [ ] Add comprehensive docstrings
- [ ] Export from `src/domain/protocols/__init__.py`

**Infrastructure Layer (Model)**:

- [ ] Create model in `src/infrastructure/persistence/models/{entity}.py`
- [ ] Extend `BaseMutableModel` (or `BaseModel` for immutable)
- [ ] Define all columns with proper types
- [ ] Add indexes for query patterns
- [ ] Add foreign key constraints
- [ ] Export from `src/infrastructure/persistence/models/__init__.py`

**Infrastructure Layer (Repository)**:

- [ ] Create in `src/infrastructure/persistence/repositories/{entity}_repository.py`
- [ ] Accept `AsyncSession` in constructor
- [ ] Implement all protocol methods
- [ ] Add `_to_domain()` mapping method
- [ ] Add `_to_model()` mapping method
- [ ] Handle nullable fields properly
- [ ] Export from `src/infrastructure/persistence/repositories/__init__.py`

**Database Migration**:

- [ ] Generate migration: `make migrate-create MSG="add {entity} table"`
- [ ] Review generated migration
- [ ] Add indexes and constraints
- [ ] Apply migration: `make migrate`

**Container Integration**:

- [ ] Add factory function in `src/core/container.py`
- [ ] Return protocol type, create implementation

**Testing**:

- [ ] Create integration tests in `tests/integration/test_{entity}_repository.py`
- [ ] Test CRUD operations
- [ ] Test query methods
- [ ] Test edge cases (not found, duplicates)
- [ ] Test foreign key relationships
- [ ] Achieve 90%+ coverage

---

**Created**: 2025-12-01 | **Last Updated**: 2025-12-01
