"""Database models for persistence layer.

This package contains SQLAlchemy/SQLModel database models that map to database
tables. These are infrastructure concerns and should not be imported by the
domain layer.

Models Organization:
    - audit_log.py: Audit trail model (immutable)
    - casbin_rule.py: Casbin RBAC policy storage
    - user.py: User model
    - session.py: Session model
    - refresh_token.py: Refresh token model
    - email_verification_token.py: Email verification token model
    - password_reset_token.py: Password reset token model
    - security_config.py: Token breach rotation config (singleton)

Note:
    Domain entities (dataclasses) live in src/domain/entities/
    Database models (SQLModel) live here in src/infrastructure/persistence/models/
    They are separate and mapped via repository layer.
"""

from src.infrastructure.persistence.models.audit_log import AuditLog
from src.infrastructure.persistence.models.casbin_rule import CasbinRule
from src.infrastructure.persistence.models.email_verification_token import (
    EmailVerificationToken,
)
from src.infrastructure.persistence.models.password_reset_token import (
    PasswordResetToken,
)
from src.infrastructure.persistence.models.provider_connection import (
    ProviderConnection as ProviderConnectionModel,
)
from src.infrastructure.persistence.models.refresh_token import RefreshToken
from src.infrastructure.persistence.models.security_config import SecurityConfig
from src.infrastructure.persistence.models.session import Session
from src.infrastructure.persistence.models.user import User

__all__ = [
    "AuditLog",
    "CasbinRule",
    "User",
    "Session",
    "RefreshToken",
    "EmailVerificationToken",
    "PasswordResetToken",
    "ProviderConnectionModel",
    "SecurityConfig",
]
