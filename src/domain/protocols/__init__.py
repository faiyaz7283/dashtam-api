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
from src.domain.protocols.authorization_protocol import AuthorizationProtocol
from src.domain.protocols.cache_keys_protocol import CacheKeysProtocol
from src.domain.protocols.cache_metrics_protocol import CacheMetricsProtocol
from src.domain.protocols.cache_protocol import CacheEntry, CacheProtocol
from src.domain.protocols.email_service_protocol import EmailServiceProtocol
from src.domain.protocols.encryption_protocol import (
    DecryptionError,
    EncryptionError,
    EncryptionKeyError,
    EncryptionProtocol,
    SerializationError,
)
from src.domain.protocols.password_hashing_protocol import PasswordHashingProtocol
from src.domain.protocols.password_reset_token_service_protocol import (
    PasswordResetTokenServiceProtocol,
)
from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol

# Repository protocols
from src.domain.protocols.balance_snapshot_repository import BalanceSnapshotRepository
from src.domain.protocols.email_verification_token_repository import (
    EmailVerificationTokenData,
    EmailVerificationTokenRepository,
)
from src.domain.protocols.password_reset_token_repository import (
    PasswordResetTokenData,
    PasswordResetTokenRepository,
)
from src.domain.protocols.refresh_token_repository import (
    RefreshTokenData,
    RefreshTokenRepository,
)
from src.domain.protocols.refresh_token_service_protocol import (
    RefreshTokenServiceProtocol,
)
from src.domain.protocols.security_config_repository import SecurityConfigRepository
from src.domain.protocols.session_cache_protocol import SessionCache
from src.domain.protocols.session_enricher_protocol import (
    DeviceEnricher,
    DeviceEnrichmentResult,
    LocationEnricher,
    LocationEnrichmentResult,
)
from src.domain.protocols.session_repository import SessionData, SessionRepository
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.holding_repository import HoldingRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_repository import ProviderRepository
from src.domain.protocols.provider_factory_protocol import ProviderFactoryProtocol
from src.domain.protocols.provider_protocol import (
    OAuthProviderProtocol,
    OAuthTokens,
    ProviderAccountData,
    ProviderHoldingData,
    ProviderProtocol,
    ProviderTransactionData,
)
from src.domain.protocols.rate_limit_protocol import RateLimitProtocol
from src.domain.protocols.sse_publisher_protocol import SSEPublisherProtocol
from src.domain.protocols.sse_subscriber_protocol import SSESubscriberProtocol
from src.domain.protocols.transaction_repository import TransactionRepository
from src.domain.protocols.user_repository import UserRepository

__all__ = [
    # Service protocols
    "AuditProtocol",
    "AuthorizationProtocol",
    "CacheEntry",
    "CacheKeysProtocol",
    "CacheMetricsProtocol",
    "CacheProtocol",
    "DecryptionError",
    "EmailServiceProtocol",
    "EncryptionError",
    "EncryptionKeyError",
    "EncryptionProtocol",
    "PasswordHashingProtocol",
    "PasswordResetTokenServiceProtocol",
    "SerializationError",
    "TokenGenerationProtocol",
    # Repository protocols
    "AccountRepository",
    "BalanceSnapshotRepository",
    "HoldingRepository",
    "EmailVerificationTokenData",
    "EmailVerificationTokenRepository",
    "PasswordResetTokenData",
    "PasswordResetTokenRepository",
    "RefreshTokenData",
    "RefreshTokenRepository",
    "RefreshTokenServiceProtocol",
    "SecurityConfigRepository",
    "UserRepository",
    # Session protocols and DTOs
    "DeviceEnricher",
    "DeviceEnrichmentResult",
    "LocationEnricher",
    "LocationEnrichmentResult",
    "SessionCache",
    "SessionData",
    "SessionRepository",
    # Rate Limit protocol
    "RateLimitProtocol",
    # Provider protocols and data types
    "OAuthProviderProtocol",
    "OAuthTokens",
    "ProviderAccountData",
    "ProviderConnectionRepository",
    "ProviderFactoryProtocol",
    "ProviderHoldingData",
    "ProviderProtocol",
    "ProviderRepository",
    "ProviderTransactionData",
    # Transaction Repository
    "TransactionRepository",
    # SSE protocols
    "SSEPublisherProtocol",
    "SSESubscriberProtocol",
]
