"""Domain value objects with validation.

Immutable value objects that enforce business constraints.
"""

from src.domain.value_objects.email import Email
from src.domain.value_objects.money import (
    VALID_CURRENCIES,
    CurrencyMismatchError,
    Money,
    validate_currency,
)
from src.domain.value_objects.password import Password
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.domain.value_objects.rate_limit_rule import RateLimitResult, RateLimitRule

__all__ = [
    "CurrencyMismatchError",
    "Email",
    "Money",
    "Password",
    "ProviderCredentials",
    "RateLimitResult",
    "RateLimitRule",
    "VALID_CURRENCIES",
    "validate_currency",
]
