"""Rate Limiting Models Package.

This package provides the abstract interface for rate limiting audit logs.
Apps implement their own database-specific models based on this interface.

Architecture:
    - Database Agnostic: Only abstract base provided
    - Framework Agnostic: No SQLModel, SQLAlchemy, or Django dependencies
    - Portable: Works with any Python app and any database
    - Interface Contract: Defines WHAT fields are needed, not HOW to store them

Exports:
    - RateLimitAuditLogBase: Abstract interface defining required fields

Usage Pattern:
    Rate limiting package provides the interface.
    Apps implement the concrete model for their database.

Example (Dashtam - PostgreSQL + SQLModel):
    >>> # In src/models/rate_limit_audit.py (Dashtam's implementation)
    >>> from sqlmodel import Field, SQLModel
    >>> from sqlalchemy.dialects.postgresql import INET
    >>> from src.rate_limiting.models import RateLimitAuditLogBase
    >>> 
    >>> class RateLimitAuditLog(SQLModel, table=True):
    ...     # Implements RateLimitAuditLogBase interface
    ...     id: UUID = Field(default_factory=uuid4, primary_key=True)
    ...     ip_address: str = Field(sa_column=Column(INET))  # PostgreSQL INET
    ...     endpoint: str = Field(...)
    ...     # ... rest of fields from base ...

Example (Other App - MySQL + Django ORM):
    >>> # In their app (Django implementation)
    >>> from django.db import models
    >>> from src.rate_limiting.models import RateLimitAuditLogBase
    >>> 
    >>> class RateLimitAuditLog(models.Model):
    ...     # Implements RateLimitAuditLogBase interface
    ...     id = models.UUIDField(primary_key=True)
    ...     ip_address = models.GenericIPAddressField()  # Django field
    ...     endpoint = models.CharField(max_length=255)
    ...     # ... rest of fields from base ...

Example (Other App - MongoDB + Pydantic):
    >>> # In their app (MongoDB implementation)
    >>> from pydantic import BaseModel
    >>> from src.rate_limiting.models import RateLimitAuditLogBase
    >>> 
    >>> class RateLimitAuditLog(BaseModel):
    ...     # Implements RateLimitAuditLogBase interface
    ...     id: UUID
    ...     ip_address: str  # Stored as string in MongoDB
    ...     endpoint: str
    ...     # ... rest of fields from base ...
"""

from src.rate_limiting.models.base import RateLimitAuditLogBase

__all__ = [
    "RateLimitAuditLogBase",  # Abstract interface (the contract)
]
