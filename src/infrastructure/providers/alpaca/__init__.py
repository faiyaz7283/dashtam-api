"""Alpaca provider package.

Provides integration with Alpaca Trading API for accounts, holdings, and transactions.
Uses API Key authentication (APCA-API-KEY-ID, APCA-API-SECRET-KEY headers).

Key Differences from OAuth Providers:
    - API Key authentication (not OAuth Bearer tokens)
    - No token exchange or refresh needed
    - Credentials are passed directly to API methods
    - Single account per API key

Reference:
    - https://docs.alpaca.markets/docs/trading-api
"""

from src.infrastructure.providers.alpaca.alpaca_provider import AlpacaProvider
from src.infrastructure.providers.alpaca.api import (
    AlpacaAccountsAPI,
    AlpacaTransactionsAPI,
)
from src.infrastructure.providers.alpaca.mappers import (
    AlpacaAccountMapper,
    AlpacaHoldingMapper,
    AlpacaTransactionMapper,
)

__all__ = [
    "AlpacaProvider",
    "AlpacaAccountsAPI",
    "AlpacaTransactionsAPI",
    "AlpacaAccountMapper",
    "AlpacaHoldingMapper",
    "AlpacaTransactionMapper",
]
