"""Chase file import provider.

Imports financial data from Chase QFX/OFX files.

Unlike API-based providers (Schwab, Alpaca), this provider:
- Parses downloaded bank statement files
- Has no live authentication (credentials contain file data)
- Returns data from the file rather than making API calls

Components:
    - ChaseFileProvider: ProviderProtocol implementation
    - QfxParser: Parses QFX/OFX file format
    - ChaseAccountMapper: Maps parsed data to ProviderAccountData
    - ChaseTransactionMapper: Maps parsed data to ProviderTransactionData
"""

from src.infrastructure.providers.chase.chase_file_provider import ChaseFileProvider
from src.infrastructure.providers.chase.mappers import (
    ChaseAccountMapper,
    ChaseTransactionMapper,
)
from src.infrastructure.providers.chase.parsers import (
    ParsedAccount,
    ParsedBalance,
    ParsedTransaction,
    QfxParser,
)

__all__ = [
    "ChaseAccountMapper",
    "ChaseFileProvider",
    "ChaseTransactionMapper",
    "ParsedAccount",
    "ParsedBalance",
    "ParsedTransaction",
    "QfxParser",
]
