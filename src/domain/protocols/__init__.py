"""Domain protocols (ports) package.

This package contains protocol definitions that the domain layer needs.
Infrastructure adapters implement these protocols without inheritance.

IMPORTANT: Re-exports are ONLY for protocols defined in this package.
Do NOT re-export from other domain subpackages (events, entities) to avoid
circular import risks.

Usage:
    # Import service protocols
    from src.domain.protocols import PasswordHashingProtocol, TokenGenerationProtocol

    # Import repository protocols
    from src.domain.protocols import UserRepository, RefreshTokenRepository
"""

# Service protocols
from src.domain.protocols.audit_protocol import AuditProtocol
from src.domain.protocols.cache_protocol import CacheEntry, CacheProtocol
from src.domain.protocols.password_hashing_protocol import PasswordHashingProtocol
from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol

# Repository protocols
from src.domain.protocols.email_verification_token_repository import (
    EmailVerificationTokenData,
    EmailVerificationTokenRepository,
)
from src.domain.protocols.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from src.domain.protocols.refresh_token_repository import (
    RefreshTokenData,
    RefreshTokenRepository,
)
from src.domain.protocols.user_repository import UserRepository

__all__ = [
    # Service protocols
    "AuditProtocol",
    "CacheEntry",
    "CacheProtocol",
    "PasswordHashingProtocol",
    "TokenGenerationProtocol",
    # Repository protocols
    "EmailVerificationTokenData",
    "EmailVerificationTokenRepository",
    "PasswordResetTokenRepository",
    "RefreshTokenData",
    "RefreshTokenRepository",
    "UserRepository",
]
