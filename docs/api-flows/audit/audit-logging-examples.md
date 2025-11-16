# Audit Logging Examples

## Overview

This document provides code examples for using the audit trail system in Dashtam.
The audit system records security-relevant events for PCI-DSS, SOC 2, and GDPR compliance.

**Key Concepts**:

- **Immutable**: Audit logs cannot be modified or deleted
- **Protocol-based**: Use `AuditProtocol` for database independence
- **Result types**: All operations return `Result[T, E]` (no exceptions)
- **JSONB context**: Flexible metadata storage without schema changes

---

## Prerequisites

- F0.9 Audit Trail feature implemented
- Database migrations applied (`alembic upgrade head`)
- Container provides `get_audit()` dependency

---

## Recording Audit Events

### Example 1: User Login (Authentication Event)

```python
from src.domain.protocols import AuditProtocol
from src.domain.enums import AuditAction
from src.core.container import get_audit
from fastapi import Depends, Request

@router.post("/auth/login")
async def login(
    data: LoginRequest,
    request: Request,
    audit: AuditProtocol = Depends(get_audit),
):
    """Login endpoint with audit logging."""
    
    # Attempt authentication
    result = await auth_service.login(data.email, data.password)
    
    match result:
        case Success(user):
            # Record successful login
            await audit.record(
                action=AuditAction.USER_LOGIN,
                resource_type="session",
                user_id=user.id,
                ip_address=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                context={
                    "method": "password",
                    "mfa": False,
                },
            )
            return {"access_token": create_token(user)}
        
        case Failure(error):
            # Record failed login attempt
            await audit.record(
                action=AuditAction.USER_LOGIN_FAILED,
                resource_type="session",
                user_id=None,  # Unknown user
                ip_address=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                context={
                    "reason": "invalid_credentials",
                    "email": data.email,  # For correlation
                },
            )
            raise HTTPException(401, "Invalid credentials")
```

### Example 2: Data Access (GDPR Compliance)

```python
@router.get("/accounts/{account_id}")
async def get_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Get account with audit trail."""
    
    # Fetch account
    account = await account_repo.find_by_id(account_id)
    
    # Record data access (GDPR requirement)
    await audit.record(
        action=AuditAction.DATA_VIEWED,
        resource_type="account",
        user_id=user.id,
        resource_id=account_id,
        context={
            "data_type": "financial",
            "fields_accessed": ["balance", "transactions"],
        },
    )
    
    return account
```

### Example 3: Provider Connection (PCI-DSS)

```python
@router.post("/providers/schwab/connect")
async def connect_schwab(
    credentials: SchwabCredentials,
    user: User = Depends(get_current_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Connect Schwab provider with audit logging."""
    
    # Connect provider
    result = await schwab_service.connect(user.id, credentials)
    
    match result:
        case Success(provider):
            # Record provider connection (PCI-DSS: cardholder data access)
            await audit.record(
                action=AuditAction.PROVIDER_CONNECTED,
                resource_type="provider",
                user_id=user.id,
                resource_id=provider.id,
                context={
                    "provider_name": "schwab",
                    "connection_method": "oauth",
                },
            )
            return {"provider_id": provider.id}
        
        case Failure(error):
            # Record failed connection attempt
            await audit.record(
                action=AuditAction.PROVIDER_TOKEN_REFRESH_FAILED,
                resource_type="provider",
                user_id=user.id,
                context={
                    "provider_name": "schwab",
                    "error_code": error.code,
                },
            )
            raise HTTPException(500, "Connection failed")
```

### Example 4: Administrative Action (SOC 2)

```python
@router.post("/admin/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    reason: str,
    admin: User = Depends(get_admin_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Suspend user with audit trail."""
    
    # Suspend user
    await user_service.suspend(user_id)
    
    # Record administrative action (SOC 2 requirement)
    await audit.record(
        action=AuditAction.ADMIN_USER_SUSPENDED,
        resource_type="user",
        user_id=admin.id,  # Admin who performed action
        resource_id=user_id,  # User being suspended
        context={
            "suspended_by": admin.email,
            "reason": reason,
            "duration": "indefinite",
        },
    )
    
    return {"status": "suspended"}
```

### Example 5: System Action (No User)

```python
async def automated_backup():
    """Scheduled backup job with audit logging."""
    
    audit = get_audit()
    
    # Perform backup
    backup_result = await backup_service.create_backup()
    
    # Record system action (no user_id)
    await audit.record(
        action=AuditAction.ADMIN_BACKUP_CREATED,
        resource_type="system",
        user_id=None,  # System action
        context={
            "backup_type": "automated",
            "backup_size": backup_result.size_bytes,
            "backup_location": "s3://backups/2025-11-16",
        },
    )
```

---

## Querying Audit Logs

### Example 6: Query User Activity

```python
from datetime import datetime, timedelta, UTC

@router.get("/audit/my-activity")
async def get_my_activity(
    user: User = Depends(get_current_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Get audit logs for current user."""
    
    # Query last 30 days
    start_date = datetime.now(UTC) - timedelta(days=30)
    
    result = await audit.query(
        user_id=user.id,
        start_date=start_date,
        limit=100,
        offset=0,
    )
    
    match result:
        case Success(logs):
            return {"logs": logs, "count": len(logs)}
        case Failure(error):
            raise HTTPException(500, error.message)
```

### Example 7: Query by Action Type

```python
@router.get("/audit/failed-logins")
async def get_failed_logins(
    admin: User = Depends(get_admin_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Get all failed login attempts (admin only)."""
    
    result = await audit.query(
        action=AuditAction.USER_LOGIN_FAILED,
        start_date=datetime.now(UTC) - timedelta(hours=24),
        limit=1000,
    )
    
    match result:
        case Success(logs):
            return {
                "failed_logins": logs,
                "count": len(logs),
            }
        case Failure(error):
            raise HTTPException(500, error.message)
```

### Example 8: Query with Pagination

```python
@router.get("/audit/provider-events")
async def get_provider_events(
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    audit: AuditProtocol = Depends(get_audit),
):
    """Get provider-related audit logs with pagination."""
    
    offset = (page - 1) * page_size
    
    result = await audit.query(
        user_id=user.id,
        resource_type="provider",
        limit=page_size,
        offset=offset,
    )
    
    match result:
        case Success(logs):
            return {
                "logs": logs,
                "page": page,
                "page_size": page_size,
                "has_more": len(logs) == page_size,
            }
        case Failure(error):
            raise HTTPException(500, error.message)
```

---

## Integration with Domain Events

### Example 9: Audit via Domain Events

```python
# src/application/events/handlers/audit_event_handler.py
from src.domain.events import UserPasswordChanged
from src.domain.protocols import AuditProtocol
from src.domain.enums import AuditAction

class AuditEventHandler:
    """Audit handler that subscribes to domain events."""
    
    def __init__(self, audit: AuditProtocol):
        self.audit = audit
    
    async def on_password_changed(self, event: UserPasswordChanged):
        """Record password change in audit trail."""
        await self.audit.record(
            action=AuditAction.USER_PASSWORD_CHANGED,
            resource_type="user",
            user_id=event.user_id,
            resource_id=event.user_id,
            context={
                "initiated_by": event.initiated_by,  # "user" or "admin"
                "method": event.method,  # "self_service", "admin_reset"
                "event_id": str(event.event_id),
            },
        )
```

---

## Error Handling

### Example 10: Handling Audit Failures

```python
@router.post("/accounts/{account_id}/delete")
async def delete_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    audit: AuditProtocol = Depends(get_audit),
    logger = Depends(get_logger),
):
    """Delete account with audit logging."""
    
    # Record audit BEFORE deletion
    audit_result = await audit.record(
        action=AuditAction.DATA_DELETED,
        resource_type="account",
        user_id=user.id,
        resource_id=account_id,
        context={
            "deletion_type": "hard",
            "reason": "user_request",
        },
    )
    
    # Log audit failures (but don't block operation)
    match audit_result:
        case Success():
            pass
        case Failure(error):
            # Log error but continue (audit is non-blocking)
            logger.error(
                "audit_failed",
                user_id=user.id,
                error=error.message,
            )
    
    # Proceed with deletion
    await account_service.delete(account_id)
    
    return {"status": "deleted"}
```

---

## Testing

### Example 11: Testing with Audit

```python
# tests/integration/test_account_deletion.py
import pytest
from src.domain.enums import AuditAction

async def test_account_deletion_creates_audit_log(
    client,
    test_user,
    test_account,
    isolated_database_session,
):
    """Test account deletion creates audit log."""
    
    # Delete account
    response = client.delete(
        f"/accounts/{test_account.id}",
        headers={"Authorization": f"Bearer {test_user.token}"},
    )
    
    assert response.status_code == 200
    
    # Verify audit log created
    from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter
    audit = PostgresAuditAdapter(session=isolated_database_session)
    
    result = await audit.query(
        user_id=test_user.id,
        action=AuditAction.DATA_DELETED,
    )
    
    assert isinstance(result, Success)
    assert len(result.value) == 1
    assert result.value[0]["resource_id"] == str(test_account.id)
```

---

## Best Practices

### DO

- ✅ Record all authentication events (login, logout, failed attempts)
- ✅ Record all data access (view, export, delete, modify)
- ✅ Record provider connections and token operations
- ✅ Record administrative actions
- ✅ Include IP address and user agent for security events
- ✅ Use descriptive context metadata
- ✅ Handle audit failures gracefully (log but don't block)

### DON'T

- ❌ Don't record passwords or tokens in context
- ❌ Don't skip audit for "minor" operations (everything is auditable)
- ❌ Don't rely on audit as primary application logging
- ❌ Don't query audit logs in performance-critical paths
- ❌ Don't attempt to modify or delete audit records

---

## Compliance Mapping

| Action Type | Compliance | Requirement |
| ----------- | ---------- | ----------- |
| USER_LOGIN | PCI-DSS 10.2.5 | Authentication mechanisms |
| USER_LOGIN_FAILED | PCI-DSS 10.2.4 | Invalid access attempts |
| DATA_VIEWED | GDPR Art. 30 | Personal data processing |
| DATA_EXPORTED | GDPR Art. 15 | Right to data portability |
| DATA_DELETED | GDPR Art. 17 | Right to be forgotten |
| PROVIDER_CONNECTED | PCI-DSS 10.2 | Cardholder data access |
| ACCESS_DENIED | SOC 2 CC6.1 | Access control failures |
| ADMIN_* | SOC 2 CC6.2 | Administrative access |

---

## Troubleshooting

### Audit logs not appearing

**Check**:

1. Migration applied? `alembic current`
2. Container configured? `get_audit()` returns PostgresAuditAdapter
3. Database connection? Check `DATABASE_URL` in `.env`
4. Result handling? Check for `Failure` case

### Performance impact

**Solutions**:

- Audit operations are async and non-blocking
- Use separate audit session (F0.9.1) when implemented
- Don't query audit logs in hot paths
- Use indexes (user_id, action, resource_type, created_at)

---

**Created**: 2025-11-16 | **Last Updated**: 2025-11-16
