# Audit Trail Architecture

## Overview

This document defines Dashtam's audit trail system for compliance with PCI-DSS,
SOC 2, and GDPR requirements. The audit trail provides an **immutable,
tamper-proof record** of all security-relevant actions for forensics and
compliance auditing.

**Key Distinction**: This is **compliance auditing** for legal/regulatory
requirements. For technical debugging, see `structured-logging-architecture.md`.
For workflow coordination, see `domain-events-architecture.md`.

---

## 1. Key Principles

### 1.1 Core Principles

- ✅ **Hexagonal Architecture**: Domain defines protocol (port), infrastructure
  provides database-agnostic adapters
- ✅ **Database Freedom**: NOT coupled to PostgreSQL - works with any SQL
  database
- ✅ **Immutability**: Records CANNOT be modified or deleted (enforced by
  database)
- ✅ **Compliance First**: PCI-DSS, SOC 2, GDPR requirements baked in
- ✅ **7+ Year Retention**: Legal requirement for financial data
- ✅ **Tamper-Proof**: Append-only, immutable records with timestamps
- ✅ **Extensibility**: JSONB metadata for new fields without schema changes
- ✅ **Performance**: Async operations, indexed queries, partitioned tables

### 1.2 Audit vs Logging vs Events

Three **separate** concerns with different purposes:

| Concern | Purpose | Storage | Retention | Query Pattern |
| ------- | ------- | ------- | --------- | ------------- |
| **Audit** | Compliance forensics | SQL Database | 7+ years | SQL |
| **Logging** | Technical debugging | CloudWatch | 30-90 days | grep |
| **Events** | Workflow coordination | In-memory | N/A | pub/sub |

**Why separate?**

- Different retention (7+ years vs 30 days vs none)
- Different query patterns (SQL vs grep vs subscription)
- Different compliance (required vs optional vs internal)
- Different access (auditors vs engineers vs system)

### 1.3 Compliance Requirements

**PCI-DSS Requirements**:

- Audit all access to cardholder data
- Track all authentication attempts
- Record all administrative actions
- 7+ year retention for audit logs
- Tamper-proof, immutable records

**SOC 2 Requirements**:

- Audit all security-relevant events
- Track who accessed what, when, where
- Immutable audit trail
- Quarterly audit log reviews

**GDPR Requirements**:

- Audit all personal data access
- Track data subject requests (export, deletion)
- Record consent changes
- Data breach notification tracking

---

## 2. Hexagonal Architecture

### 2.1 Layer Responsibilities

```text
┌─────────────────────────────────────────────────────────┐
│ Domain Layer (Port/Protocol)                            │
│ - AuditProtocol defines interface                       │
│ - AuditAction enum (extensible)                         │
│ - Pure Python (no database imports)                     │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ implements
                          │
┌─────────────────────────────────────────────────────────┐
│ Infrastructure Layer (Database-Agnostic Adapters)       │
│ - PostgresAuditAdapter (uses rules for immutability)    │
│ - MySQLAuditAdapter (uses triggers for immutability)    │
│ - SQLiteAuditAdapter (testing - uses constraints)       │
│ - Each adapter implements immutability its own way      │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ uses
                          │
┌─────────────────────────────────────────────────────────┐
│ Core Layer (Container)                                  │
│ - get_audit() creates correct adapter                   │
│ - Reads DATABASE_TYPE env var (postgres/mysql/sqlite)   │
│ - Follows Composition Root pattern                      │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ uses
                          │
┌─────────────────────────────────────────────────────────┐
│ Application Layer (Event Handlers, Services)            │
│ - Inject AuditProtocol via Depends()                    │
│ - Record security-relevant actions                      │
│ - Add context (IP, user agent, metadata)                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Flow

- **Domain** → Defines `AuditProtocol` + `AuditAction` enum (no dependencies)
- **Infrastructure** → Implements protocol with database-specific adapters
- **Core/Container** → Creates correct adapter based on `DATABASE_TYPE`
- **Application** → Consumes audit via protocol (database-agnostic)

**Benefits**:

- Domain layer remains pure (no SQLAlchemy/SQLModel imports)
- Easy to swap databases (Postgres → MySQL → SQLite)
- Testable (mock protocol, in-memory adapter for tests)
- Configuration-driven (change database via env var)

### 2.3 Database

**Each adapter implements immutability differently**:

| Database | Immutability Strategy |
| -------- | --------------------- |
| **PostgreSQL** | RULES (block UPDATE/DELETE) |
| **MySQL** | TRIGGERS (block UPDATE/DELETE) |
| **SQLite** | Constraints + app-level enforcement (testing) |
| **In-Memory** | Simple list append (unit tests) |

**Protocol doesn't care HOW** - it just says "record this audit entry".

---

## 3. Domain Layer - Protocol Definition

### 3.1 AuditAction Enum

**File**: `src/domain/enums/audit_action.py`

**Architectural Decision**: Following centralized enum pattern (see
`docs/architecture/directory-structure.md` - Enum Organization section).
All domain enums live in `src/domain/enums/` for discoverability and
maintainability.

```python
# src/domain/enums/audit_action.py
"""Audit action types for compliance tracking.

This enum defines all auditable actions in the system (PCI-DSS, SOC 2, GDPR).
Extensible via enum values - no database schema changes needed.

Categories:
- Authentication (USER_*)
- Authorization (ACCESS_*)
- Data Operations (DATA_*)
- Administrative (ADMIN_*)
- Provider (PROVIDER_*)
"""

from enum import Enum


class AuditAction(str, Enum):
    """Audit action types (extensible via enum).
    
    Organized by category for clarity. Add new actions as needed
    without database schema changes (metadata stores action-specific data).
    
    Categories:
    - Authentication (USER_*)
    - Authorization (ACCESS_*)
    - Data Operations (DATA_*)
    - Administrative (ADMIN_*)
    - Provider (PROVIDER_*)
    """
    
    # Authentication events (PCI-DSS required)
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_REGISTERED = "user_registered"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_PASSWORD_RESET_REQUESTED = "user_password_reset_requested"
    USER_PASSWORD_RESET_COMPLETED = "user_password_reset_completed"
    USER_EMAIL_VERIFIED = "user_email_verified"
    USER_MFA_ENABLED = "user_mfa_enabled"
    USER_MFA_DISABLED = "user_mfa_disabled"
    
    # Authorization events (SOC 2 required)
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    
    # Data access events (GDPR required)
    DATA_VIEWED = "data_viewed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    DATA_MODIFIED = "data_modified"
    
    # Administrative events (SOC 2 required)
    ADMIN_USER_CREATED = "admin_user_created"
    ADMIN_USER_DELETED = "admin_user_deleted"
    ADMIN_USER_SUSPENDED = "admin_user_suspended"
    ADMIN_CONFIG_CHANGED = "admin_config_changed"
    ADMIN_BACKUP_CREATED = "admin_backup_created"
    
    # Provider events (PCI-DSS required - cardholder data access)
    PROVIDER_CONNECTED = "provider_connected"
    PROVIDER_DISCONNECTED = "provider_disconnected"
    PROVIDER_TOKEN_REFRESHED = "provider_token_refreshed"
    PROVIDER_TOKEN_REFRESH_FAILED = "provider_token_refresh_failed"
    PROVIDER_DATA_SYNCED = "provider_data_synced"
    PROVIDER_ACCOUNT_VIEWED = "provider_account_viewed"  # PCI-DSS
    PROVIDER_TRANSACTION_VIEWED = "provider_transaction_viewed"  # PCI-DSS
```

### 3.2 AuditProtocol Interface

**File**: `src/domain/protocols/audit_protocol.py`

```python
# src/domain/protocols/audit_protocol.py
from typing import Protocol, Any
from uuid import UUID
from datetime import datetime

from src.domain.enums import AuditAction
from src.domain.errors import AuditError
from src.core.result import Result


class AuditProtocol(Protocol):
    """Protocol for audit trail systems.
    
    Records immutable audit entries for compliance (PCI-DSS, SOC 2, GDPR).
    All implementations MUST ensure immutability (no updates/deletes).
    
    Implementations:
    - PostgresAuditAdapter: PostgreSQL with RULES
    - MySQLAuditAdapter: MySQL with TRIGGERS
    - SQLiteAuditAdapter: SQLite for testing
    - InMemoryAuditAdapter: Testing only
    
    Compliance:
    - PCI-DSS: 7+ year retention, immutable, tamper-proof
    - SOC 2: Security event tracking, who/what/when/where
    - GDPR: Personal data access tracking
    """
    
    async def record(
        self,
        *,
        action: AuditAction,
        user_id: UUID | None = None,
        resource_type: str,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[None, AuditError]:
        """Record an audit entry (immutable, cannot be changed).
        
        Args:
            action: What happened (enum for consistency)
            user_id: Who performed the action (None for system actions)
            resource_type: What was affected (user, account, provider)
            resource_id: Specific resource identifier
            ip_address: Where from (required for auth events)
            user_agent: Client information
            metadata: Additional context (JSONB - extensible)
            
        Returns:
            Result[None, AuditError]: Success or audit system error
            
        Example:
            await audit.record(
                action=AuditAction.USER_LOGIN,
                user_id=user_id,
                resource_type="session",
                resource_id=session_id,
                ip_address=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                metadata={"method": "password", "mfa": True},
            )
            
        Note:
            - Records are IMMUTABLE (cannot update or delete)
            - Timestamps are UTC and set by database
            - Metadata is JSONB for extensibility
        """
        ...
    
    async def query(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Result[list[dict[str, Any]], AuditError]:
        """Query audit trail (read-only, for compliance reports).
        
        Args:
            user_id: Filter by user
            action: Filter by action type
            resource_type: Filter by resource
            start_date: From date (inclusive)
            end_date: To date (inclusive)
            limit: Max results (default 100, max 1000)
            offset: Pagination offset
            
        Returns:
            Result[list[AuditEntry], AuditError]: Matching audit entries
            
        Note:
            - Used for compliance reports and forensics
            - NOT for application logic (use domain events instead)
            - Results ordered by timestamp DESC (newest first)
        """
        ...
```

### 3.2 AuditAction Enum

```python
# src/domain/enums/audit_action.py
from enum import Enum


class AuditAction(str, Enum):
    """Audit action types (extensible via enum).
    
    Organized by category for clarity. Add new actions as needed
    without database schema changes (metadata stores action-specific data).
    
    Categories:
    - Authentication (USER_*)
    - Authorization (ACCESS_*)
    - Data Operations (DATA_*)
    - Administrative (ADMIN_*)
    - Provider (PROVIDER_*)
    """
    
    # Authentication events (PCI-DSS required)
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_REGISTERED = "user_registered"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_PASSWORD_RESET_REQUESTED = "user_password_reset_requested"
    USER_PASSWORD_RESET_COMPLETED = "user_password_reset_completed"
    USER_EMAIL_VERIFIED = "user_email_verified"
    USER_MFA_ENABLED = "user_mfa_enabled"
    USER_MFA_DISABLED = "user_mfa_disabled"
    
    # Authorization events (SOC 2 required)
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    
    # Data access events (GDPR required)
    DATA_VIEWED = "data_viewed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    DATA_MODIFIED = "data_modified"
    
    # Administrative events (SOC 2 required)
    ADMIN_USER_CREATED = "admin_user_created"
    ADMIN_USER_DELETED = "admin_user_deleted"
    ADMIN_USER_SUSPENDED = "admin_user_suspended"
    ADMIN_CONFIG_CHANGED = "admin_config_changed"
    ADMIN_BACKUP_CREATED = "admin_backup_created"
    
    # Provider events (PCI-DSS required - cardholder data access)
    PROVIDER_CONNECTED = "provider_connected"
    PROVIDER_DISCONNECTED = "provider_disconnected"
    PROVIDER_TOKEN_REFRESHED = "provider_token_refreshed"
    PROVIDER_TOKEN_REFRESH_FAILED = "provider_token_refresh_failed"
    PROVIDER_DATA_SYNCED = "provider_data_synced"
    PROVIDER_ACCOUNT_VIEWED = "provider_account_viewed"  # PCI-DSS
    PROVIDER_TRANSACTION_VIEWED = "provider_transaction_viewed"  # PCI-DSS
```

### 3.3 AuditError Class

**File**: `src/domain/errors/audit_error.py`

```python
from dataclasses import dataclass
from src.core.errors import DomainError

@dataclass(frozen=True, slots=True, kw_only=True)
class AuditError(DomainError):
    """Audit system failure.
    
    Used when audit trail recording fails (database error, connection loss).
    
    Attributes:
        code: ErrorCode enum (AUDIT_RECORD_FAILED, AUDIT_QUERY_FAILED).
        message: Human-readable message.
        details: Additional context.
    """
    pass
```

**Error Codes**: Added to `src/core/enums/error_code.py`:
- `AUDIT_RECORD_FAILED` - Failed to record audit entry
- `AUDIT_QUERY_FAILED` - Failed to query audit trail

### 3.4 Required Context Fields

**MANDATORY** fields in every audit entry:

- `id` (UUID): Unique identifier (primary key)
- `action` (AuditAction): What happened (enum)
- `timestamp` (datetime): When it happened (UTC, immutable)
- `resource_type` (str): What was affected (user, account, provider)

**REQUIRED for specific actions**:

- `user_id` (UUID): Who did it (required except system actions)
- `ip_address` (str): Where from (required for auth events)
- `user_agent` (str): Client info (required for auth events)

**OPTIONAL but recommended**:

- `resource_id` (UUID): Specific resource identifier
- `metadata` (JSONB): Action-specific context (extensible)

---

## 4. Infrastructure Layer - Database Adapters

### 4.1 PostgreSQL Adapter (Production)

**File**: `src/infrastructure/audit/postgres_audit_adapter.py`

**Immutability Strategy**: PostgreSQL RULES block UPDATE/DELETE

```python
# Database migration creates immutable table
CREATE RULE audit_logs_no_update AS 
    ON UPDATE TO audit_logs 
    DO INSTEAD NOTHING;

CREATE RULE audit_logs_no_delete AS 
    ON DELETE TO audit_logs 
    DO INSTEAD NOTHING;
```

**Adapter Implementation**:

```python
from datetime import datetime, UTC
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from src.domain.protocols.audit_protocol import AuditProtocol, AuditError
from src.domain.enums import AuditAction
from src.infrastructure.persistence.models.audit import AuditLogModel
from src.core.result import Result, Success, Failure


class PostgresAuditAdapter:
    """PostgreSQL audit trail adapter with immutable records.
    
    Immutability enforced by database RULES (cannot UPDATE or DELETE).
    Uses JSONB for extensible metadata storage.
    
    Args:
        session: SQLAlchemy async session (injected)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def record(
        self,
        *,
        action: AuditAction,
        user_id: UUID | None = None,
        resource_type: str,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[None, AuditError]:
        """Record immutable audit entry in PostgreSQL."""
        try:
            audit_log = AuditLogModel(
                id=uuid4(),
                action=action.value,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata or {},
                timestamp=datetime.now(UTC),
            )
            
            self.session.add(audit_log)
            await self.session.flush()
            
            return Success(None)
            
        except Exception as e:
            return Failure(AuditError(
                code="AUDIT_RECORD_FAILED",
                message=f"Failed to record audit entry: {str(e)}",
            ))
    
    async def query(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Result[list[dict[str, Any]], AuditError]:
        """Query audit trail with filters."""
        try:
            # Build query with filters
            query = select(AuditLogModel)
            
            conditions = []
            if user_id:
                conditions.append(AuditLogModel.user_id == user_id)
            if action:
                conditions.append(AuditLogModel.action == action.value)
            if resource_type:
                conditions.append(AuditLogModel.resource_type == resource_type)
            if start_date:
                conditions.append(AuditLogModel.timestamp >= start_date)
            if end_date:
                conditions.append(AuditLogModel.timestamp <= end_date)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Order by timestamp DESC, apply pagination
            query = query.order_by(AuditLogModel.timestamp.desc())
            query = query.limit(min(limit, 1000)).offset(offset)
            
            result = await self.session.execute(query)
            records = result.scalars().all()
            
            # Convert to dict for protocol compliance
            return Success([
                {
                    "id": str(r.id),
                    "action": r.action,
                    "user_id": str(r.user_id) if r.user_id else None,
                    "resource_type": r.resource_type,
                    "resource_id": str(r.resource_id) if r.resource_id else None,
                    "ip_address": r.ip_address,
                    "user_agent": r.user_agent,
                    "metadata": r.metadata,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in records
            ])
            
        except Exception as e:
            return Failure(AuditError(
                code="AUDIT_QUERY_FAILED",
                message=f"Failed to query audit trail: {str(e)}",
            ))
```

### 4.2 Database Model (SQLModel)

```python
# src/infrastructure/persistence/models/audit.py
from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Index


class AuditLogModel(SQLModel, table=True):
    """Audit trail table - IMMUTABLE (enforced by database rules).
    
    CRITICAL: This table is append-only. Records CANNOT be modified or
    deleted due to PostgreSQL RULES in migration.
    
    Compliance:
    - PCI-DSS: 7+ year retention
    - SOC 2: Security event tracking
    - GDPR: Personal data access tracking
    """
    __tablename__ = "audit_logs"
    
    # Primary key
    id: UUID = Field(primary_key=True)
    
    # What happened
    action: str = Field(index=True, max_length=100)
    
    # Who did it
    user_id: UUID | None = Field(default=None, index=True, foreign_key="users.id")
    
    # What was affected
    resource_type: str = Field(index=True, max_length=100)
    resource_id: UUID | None = Field(default=None, index=True)
    
    # Where and how
    ip_address: str | None = Field(default=None, max_length=45)  # IPv6 max
    user_agent: str | None = Field(default=None, max_length=500)
    
    # Extensible metadata (JSONB in PostgreSQL)
    metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
    
    # When (immutable, set by database)
    timestamp: datetime = Field(index=True)
    
    __table_args__ = (
        # Composite indexes for common queries
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_timestamp", "timestamp"),
    )
```

### 4.3 Alembic Migration (Immutability Enforcement)

```python
# alembic/versions/XXXX_create_audit_logs_table.py
"""Create immutable audit_logs table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-11-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('resource_type', sa.String(100), nullable=False, index=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create composite indexes
    op.create_index('idx_audit_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    
    # CRITICAL: Enforce immutability with PostgreSQL RULES
    op.execute("""
        CREATE RULE audit_logs_no_update AS 
            ON UPDATE TO audit_logs 
            DO INSTEAD NOTHING;
    """)
    
    op.execute("""
        CREATE RULE audit_logs_no_delete AS 
            ON DELETE TO audit_logs 
            DO INSTEAD NOTHING;
    """)


def downgrade() -> None:
    # Drop rules first
    op.execute("DROP RULE IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP RULE IF EXISTS audit_logs_no_update ON audit_logs;")
    
    # Drop table
    op.drop_table('audit_logs')
```

### 4.4 Alternative: MySQL Adapter (Optional)

**Immutability Strategy**: MySQL TRIGGERS block UPDATE/DELETE

```sql
-- MySQL migration
DELIMITER $$

CREATE TRIGGER audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit logs are immutable - updates not allowed';
END$$

CREATE TRIGGER audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit logs are immutable - deletes not allowed';
END$$

DELIMITER ;
```

**Adapter** (`MySQLAuditAdapter`) would be similar to Postgres adapter but
use MySQL-specific dialect.

---

## 5. Core Layer - Container Integration

### 5.1 Container Pattern

**File**: `src/core/container.py` (add to existing file)

```python
# ============================================================================
# Audit Dependencies (Application-Scoped)
# ============================================================================

@lru_cache()
def get_audit() -> "AuditProtocol":
    """Get audit trail singleton (app-scoped).
    
    Container owns adapter selection based on DATABASE_TYPE.
    This follows the Composition Root pattern (industry best practice).
    
    Returns correct adapter based on database in use:
        - 'postgresql': PostgresAuditAdapter (immutability via RULES)
        - 'mysql': MySQLAuditAdapter (immutability via TRIGGERS)
        - 'sqlite': SQLiteAuditAdapter (testing only)
    
    Returns:
        Audit trail implementing AuditProtocol.
    
    Usage:
        # Application Layer
        audit = get_audit()
        await audit.record(action=AuditAction.USER_LOGIN, ...)
        
        # Presentation Layer (FastAPI)
        audit: AuditProtocol = Depends(get_audit)
    """
    from src.domain.protocols.audit_protocol import AuditProtocol
    
    # Determine database type from settings
    db_type = settings.database_url.split("://")[0]
    
    if db_type.startswith("postgresql"):
        from src.infrastructure.audit.postgres_audit_adapter import PostgresAuditAdapter
        # Note: In real usage, get session from request scope
        # This is simplified for illustration
        return PostgresAuditAdapter(session=get_database().session)
    
    elif db_type.startswith("mysql"):
        from src.infrastructure.audit.mysql_audit_adapter import MySQLAuditAdapter
        return MySQLAuditAdapter(session=get_database().session)
    
    else:
        raise ValueError(f"Unsupported database type for audit: {db_type}")


def clear_container_cache() -> None:
    """Clear all container caches (testing utility)."""
    get_cache.cache_clear()
    get_secrets.cache_clear()
    get_database.cache_clear()
    get_logger.cache_clear()
    get_audit.cache_clear()  # Add audit to cache clearing
```

---

## 6. Application Layer Integration

### 6.1 Using Audit in Services

```python
# src/application/services/auth_service.py
from src.domain.protocols.audit_protocol import AuditProtocol
from src.domain.enums import AuditAction


class AuthService:
    def __init__(self, audit: AuditProtocol):
        self.audit = audit
    
    async def login_user(
        self, 
        email: str, 
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> Result[User, AuthError]:
        """Authenticate user and record audit trail."""
        
        # Attempt authentication
        result = await self.user_repo.find_by_email(email)
        
        match result:
            case Success(user):
                if verify_password(password, user.password_hash):
                    # Success - record audit
                    await self.audit.record(
                        action=AuditAction.USER_LOGIN,
                        user_id=user.id,
                        resource_type="session",
                        ip_address=ip_address,
                        user_agent=user_agent,
                        metadata={"method": "password"},
                    )
                    return Success(user)
                else:
                    # Failed login - record audit (security event)
                    await self.audit.record(
                        action=AuditAction.USER_LOGIN_FAILED,
                        user_id=user.id,
                        resource_type="session",
                        ip_address=ip_address,
                        user_agent=user_agent,
                        metadata={"reason": "invalid_password"},
                    )
                    return Failure(AuthError("Invalid credentials"))
            
            case Failure(_):
                # User not found - record audit (security event)
                await self.audit.record(
                    action=AuditAction.USER_LOGIN_FAILED,
                    user_id=None,  # Unknown user
                    resource_type="session",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={"reason": "user_not_found", "email": email},
                )
                return Failure(AuthError("Invalid credentials"))
```

### 6.2 Integration with Domain Events

```python
# src/application/events/handlers/audit_event_handler.py
from src.domain.events.user_password_changed import UserPasswordChanged
from src.domain.protocols.audit_protocol import AuditProtocol
from src.domain.enums import AuditAction
from src.domain.enums.audit_action import AuditAction


class AuditEventHandler:
    """Domain event handler that creates audit records.
    
    Listens to domain events and records them in audit trail.
    Decouples audit from business logic.
    """
    
    def __init__(self, audit: AuditProtocol):
        self.audit = audit
    
    async def on_password_changed(self, event: UserPasswordChanged) -> None:
        """Record password change in audit trail."""
        await self.audit.record(
            action=AuditAction.USER_PASSWORD_CHANGED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            metadata={
                "initiated_by": event.initiated_by,  # user or admin
                "event_id": str(event.event_id),
            },
        )
```

### 6.3 FastAPI Endpoint Example

```python
# src/presentation/api/v1/auth.py
from fastapi import APIRouter, Depends, Request

from src.domain.protocols.audit_protocol import AuditProtocol
from src.core.container import get_audit


router = APIRouter()


@router.post("/login")
async def login(
    data: LoginRequest,
    request: Request,
    audit: AuditProtocol = Depends(get_audit),
):
    """User login with automatic audit trail."""
    
    # Extract context
    ip_address = request.client.host
    user_agent = request.headers.get("User-Agent", "unknown")
    
    # Authenticate (service records audit internally)
    result = await auth_service.login_user(
        email=data.email,
        password=data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    match result:
        case Success(user):
            return {"access_token": create_token(user)}
        case Failure(error):
            raise HTTPException(401, detail=error.message)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests (Domain/Application)

```python
# tests/unit/test_domain_audit_protocol.py
from unittest.mock import AsyncMock

from src.domain.protocols.audit_protocol import AuditProtocol
from src.domain.enums import AuditAction
from src.domain.enums.audit_action import AuditAction


async def test_audit_protocol_mocking():
    """Test that AuditProtocol can be easily mocked."""
    # Create mock audit
    mock_audit = AsyncMock(spec=AuditProtocol)
    
    # Use in service
    service = AuthService(audit=mock_audit)
    
    # Verify audit.record was called
    mock_audit.record.assert_called_once_with(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        metadata={"method": "password"},
    )
```

### 7.2 Integration Tests (Infrastructure)

```python
# tests/integration/test_audit_postgres_adapter.py
import pytest
from datetime import datetime, UTC

from src.infrastructure.audit.postgres_audit_adapter import PostgresAuditAdapter
from src.domain.enums import AuditAction


@pytest.mark.integration
async def test_audit_record_creates_immutable_entry(db_session):
    """Test audit adapter creates immutable records."""
    adapter = PostgresAuditAdapter(session=db_session)
    
    # Record audit entry
    result = await adapter.record(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
        ip_address="192.168.1.1",
        user_agent="Test Agent",
        metadata={"test": True},
    )
    
    assert result.is_success()
    
    # Verify record exists
    query_result = await adapter.query(user_id=user_id, limit=1)
    assert len(query_result.value) == 1
    
    entry = query_result.value[0]
    assert entry["action"] == "user_login"
    assert entry["user_id"] == str(user_id)


@pytest.mark.integration
async def test_audit_immutability_enforced(db_session):
    """Test that audit records CANNOT be updated or deleted."""
    adapter = PostgresAuditAdapter(session=db_session)
    
    # Create entry
    result = await adapter.record(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
    )
    
    # Attempt UPDATE (should be blocked by RULE)
    # This test verifies database-level immutability
    with pytest.raises(Exception):  # PostgreSQL blocks with RULE
        await db_session.execute(
            "UPDATE audit_logs SET action = 'hacked' WHERE user_id = :user_id",
            {"user_id": user_id},
        )
    
    # Attempt DELETE (should be blocked by RULE)
    with pytest.raises(Exception):  # PostgreSQL blocks with RULE
        await db_session.execute(
            "DELETE FROM audit_logs WHERE user_id = :user_id",
            {"user_id": user_id},
        )
```

### 7.3 Test Coverage Target

- **Unit tests**: 90%+ coverage (protocol mocking, enum validation)
- **Integration tests**: 85%+ coverage (database operations, immutability)
- **Total coverage**: 85%+ for audit infrastructure

---

## 8. Compliance & Security

### 8.1 PCI-DSS Compliance Checklist

- ✅ All cardholder data access logged (PROVIDER_ACCOUNT_VIEWED)
- ✅ All authentication attempts logged (USER_LOGIN, USER_LOGIN_FAILED)
- ✅ All administrative actions logged (ADMIN_*)
- ✅ 7+ year retention configured
- ✅ Immutable records (cannot be tampered with)
- ✅ Quarterly audit log review process (manual)

### 8.2 SOC 2 Compliance Checklist

- ✅ Security-relevant events logged
- ✅ Who/what/when/where tracking (user_id, action, timestamp, ip_address)
- ✅ Tamper-proof audit trail (immutable)
- ✅ Access controls (only auditors query audit trail)
- ✅ Regular audit log reviews

### 8.3 GDPR Compliance Checklist

- ✅ Personal data access logged (DATA_VIEWED, DATA_EXPORTED)
- ✅ Data deletion logged (DATA_DELETED)
- ✅ Consent changes logged (metadata)
- ✅ Data breach notification tracking (ADMIN actions)
- ✅ User can request audit trail of their data

### 8.4 Retention Policy

```python
# Retention configuration
AUDIT_RETENTION_YEARS = 7  # Minimum for PCI-DSS

# Database partitioning (PostgreSQL)
# Partition by year for efficient retention management
CREATE TABLE audit_logs_2025 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

# Retention job (runs annually)
# Archive old partitions to cold storage, keep for 7+ years
```

---

## 9. Performance Optimization

### 9.1 Indexing Strategy

**Indexes on `audit_logs` table**:

- `timestamp` (DESC) - Most queries filter by date range
- `user_id`, `action` - Composite index for user activity reports
- `resource_type`, `resource_id` - Composite index for resource audits
- `action` - Compliance reports by event type

### 9.2 Table Partitioning

**Partition by year** (PostgreSQL):

```sql
-- Create partitioned table
CREATE TABLE audit_logs (
    ...
) PARTITION BY RANGE (timestamp);

-- Create partition per year
CREATE TABLE audit_logs_2025 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE audit_logs_2026 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
```

**Benefits**:

- Query performance (scan only relevant partition)
- Easy archival (detach old partition, archive to S3)
- Retention management (keep 7+ years, archive older)

### 9.3 Async Operations

**All audit operations are async** (non-blocking):

```python
# Don't wait for audit to complete
await audit.record(...)  # Returns immediately (async)

# Business logic continues
return {"status": "success"}
```

### 9.4 Query Limits

- Default limit: 100 records
- Maximum limit: 1000 records (prevent DoS)
- Pagination: Use `limit`/`offset` for large result sets

---

## 10. Operational Procedures

### 10.1 Audit Log Review (Quarterly)

**Process**:

1. Export audit logs for quarter:

```python
# Generate compliance report
result = await audit.query(
    start_date=quarter_start,
    end_date=quarter_end,
    limit=10000,
)
```

1. Review for anomalies:
   - Unusual login patterns
   - Failed auth attempts
   - Admin actions
   - Data exports

1. Document findings in compliance report

### 10.2 Incident Response

**When security incident occurs**:

1. Query audit trail for affected time range
2. Identify all affected users/resources
3. Preserve audit records (immutable, no risk of tampering)
4. Generate incident report from audit data

```python
# Incident investigation
result = await audit.query(
    start_date=incident_start,
    end_date=incident_end,
    resource_type="account",
    limit=1000,
)
```

### 10.3 Data Retention

**Archival process** (after 7+ years):

1. Detach old partition
2. Export to cold storage (S3 Glacier)
3. Keep for legal requirement (varies by jurisdiction)
4. Eventually delete after legal retention expires

---

## 11. Migration Path

### 11.1 Initial Migration

```bash
# Create audit_logs table with immutability
alembic upgrade head
```

### 11.2 Adding New AuditActions

**NO database migration needed** - just add to enum:

```python
# src/domain/enums/audit_action.py

class AuditAction(str, Enum):
    # ... existing actions ...
    
    # NEW: Just add to enum
    USER_PROFILE_UPDATED = "user_profile_updated"
```

**Action-specific metadata goes in JSONB**:

```python
await audit.record(
    action=AuditAction.USER_PROFILE_UPDATED,
    user_id=user_id,
    resource_type="user",
    resource_id=user_id,
    metadata={
        "fields_changed": ["email", "phone"],
        "old_email": "old@example.com",
        "new_email": "new@example.com",
    },
)
```

---

## 12. Future Enhancements

### 12.1 Cryptographic Integrity

**Future**: Add cryptographic chain for tamper detection

```python
# Each audit entry includes hash of previous entry
# Detect if database is tampered with at OS/filesystem level
previous_hash = sha256(previous_entry)
current_entry.previous_hash = previous_hash
```

### 12.2 Compliance Dashboards

**Future**: Real-time compliance dashboards

- Failed login attempts (last 24 hours)
- Admin actions (last week)
- Data exports (by user)
- PCI-DSS compliance score

### 12.3 Automated Anomaly Detection

**Future**: ML-based anomaly detection

- Unusual login patterns
- Geographic anomalies
- Bulk data exports
- Time-based anomalies (logins at 3 AM)

---

**Created**: 2025-11-14 | **Last Updated**: 2025-11-14
