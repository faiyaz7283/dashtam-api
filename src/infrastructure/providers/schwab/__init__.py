"""Schwab provider package.

Implements ProviderProtocol for Charles Schwab integration.

Architecture:
    schwab_provider.py - Main provider implementing ProviderProtocol
    api/ - HTTP clients for Schwab API endpoints
    mappers/ - Data transformers (JSON → ProviderAccountData/ProviderTransactionData)

Usage:
    from src.infrastructure.providers.schwab import SchwabProvider

    provider = SchwabProvider(settings=settings)
    result = await provider.exchange_code_for_tokens(auth_code)
"""

from src.infrastructure.providers.schwab.schwab_provider import SchwabProvider
from src.infrastructure.providers.schwab.api.accounts_api import SchwabAccountsAPI
from src.infrastructure.providers.schwab.api.transactions_api import (
    SchwabTransactionsAPI,
)
from src.infrastructure.providers.schwab.mappers.account_mapper import (
    SchwabAccountMapper,
)
from src.infrastructure.providers.schwab.mappers.transaction_mapper import (
    SchwabTransactionMapper,
)

__all__ = [
    "SchwabProvider",
    "SchwabAccountsAPI",
    "SchwabTransactionsAPI",
    "SchwabAccountMapper",
    "SchwabTransactionMapper",
]
