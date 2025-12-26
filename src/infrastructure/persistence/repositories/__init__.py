"""Repository implementations (adapters for hexagonal architecture).

This package contains concrete implementations of repository protocols
defined in the domain layer.
"""

from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.balance_snapshot_repository import (
    BalanceSnapshotRepository,
)
from src.infrastructure.persistence.repositories.holding_repository import (
    HoldingRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.email_verification_token_repository import (
    EmailVerificationTokenRepository,
)
from src.infrastructure.persistence.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from src.infrastructure.persistence.repositories.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.infrastructure.persistence.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.infrastructure.persistence.repositories.security_config_repository import (
    SecurityConfigRepository,
)
from src.infrastructure.persistence.repositories.session_repository import (
    SessionRepository,
)
from src.infrastructure.persistence.repositories.user_repository import UserRepository

__all__ = [
    "AccountRepository",
    "BalanceSnapshotRepository",
    "EmailVerificationTokenRepository",
    "HoldingRepository",
    "PasswordResetTokenRepository",
    "ProviderConnectionRepository",
    "RefreshTokenRepository",
    "SecurityConfigRepository",
    "SessionRepository",
    "TransactionRepository",
    "UserRepository",
]
