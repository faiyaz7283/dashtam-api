"""Chase file import provider implementing ProviderProtocol.

Parses QFX/OFX files exported from Chase online banking.

Unlike API-based providers (Schwab, Alpaca), this provider:
- Receives file content via credentials dict (not OAuth/API keys)
- Parses local file data (no HTTP requests)
- Has no token refresh (files don't expire)

Credentials Dict Structure:
    {
        "file_content": bytes,      # Raw QFX file content
        "file_format": "qfx",       # Format identifier
        "file_name": "Chase.QFX",   # Original filename (for logging)
    }

Architecture:
    ChaseFileProvider orchestrates:
    - parsers/qfx_parser.py: Parses QFX/OFX file format
    - mappers/account_mapper.py: ParsedAccount → ProviderAccountData
    - mappers/transaction_mapper.py: ParsedTransaction → ProviderTransactionData

Reference:
    - docs/architecture/provider-integration-architecture.md
"""

from datetime import date
from typing import Any

import structlog

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import ProviderError, ProviderInvalidResponseError
from src.domain.protocols.provider_protocol import (
    ProviderAccountData,
    ProviderHoldingData,
    ProviderTransactionData,
)
from src.infrastructure.providers.chase.mappers.account_mapper import (
    ChaseAccountMapper,
)
from src.infrastructure.providers.chase.mappers.transaction_mapper import (
    ChaseTransactionMapper,
)
from src.infrastructure.providers.chase.parsers.qfx_parser import (
    ParsedAccount,
    QfxParser,
)

logger = structlog.get_logger(__name__)


class ChaseFileProvider:
    """Chase file import provider implementing ProviderProtocol.

    Parses QFX/OFX files from Chase bank and returns structured data.
    Unlike API providers, this receives file content in credentials dict.

    Key Differences from API Providers:
    - Credentials contain file_content (bytes) instead of tokens/keys
    - No HTTP requests - all data comes from parsed file
    - fetch_accounts returns single account per file (Chase exports one per file)
    - fetch_transactions returns transactions embedded in same file
    - No token refresh needed

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> provider = ChaseFileProvider()
        >>> credentials = {
        ...     "file_content": open("Chase.QFX", "rb").read(),
        ...     "file_format": "qfx",
        ...     "file_name": "Chase0737_Activity.QFX",
        ... }
        >>> result = await provider.fetch_accounts(credentials)
        >>> match result:
        ...     case Success(accounts):
        ...         print(f"Found {len(accounts)} account(s)")
        ...     case Failure(error):
        ...         print(f"Failed: {error.message}")
    """

    def __init__(self) -> None:
        """Initialize Chase file provider."""
        self._parser = QfxParser()
        self._account_mapper = ChaseAccountMapper()
        self._transaction_mapper = ChaseTransactionMapper()

        # Cache parsed data within a single request
        # Key: hash of file_content, Value: ParsedAccount
        self._parsed_cache: dict[int, ParsedAccount] = {}

    @property
    def slug(self) -> str:
        """Return provider slug identifier."""
        return "chase_file"

    async def fetch_accounts(
        self,
        credentials: dict[str, Any],
    ) -> Result[list[ProviderAccountData], ProviderError]:
        """Fetch account from parsed QFX file.

        Chase exports one account per QFX file, so this returns a single-item list.

        Args:
            credentials: Dict containing:
                - file_content: Raw QFX file bytes
                - file_format: Format identifier ("qfx" or "ofx")
                - file_name: Original filename (optional, for logging)

        Returns:
            Success(list[ProviderAccountData]): Single account from file.
            Failure(ProviderInvalidResponseError): If file is invalid or unparseable.
        """
        # Parse file (with caching)
        parsed_result = self._parse_file(credentials)
        if isinstance(parsed_result, Failure):
            return Failure(error=parsed_result.error)

        parsed = parsed_result.value

        # Map to ProviderAccountData
        account_data = self._account_mapper.map_account(parsed)

        logger.info(
            "chase_file_fetch_accounts_succeeded",
            provider=self.slug,
            account_id_masked=account_data.account_number_masked,
            account_type=account_data.account_type,
        )

        return Success(value=[account_data])

    async def fetch_transactions(
        self,
        credentials: dict[str, Any],
        provider_account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Result[list[ProviderTransactionData], ProviderError]:
        """Fetch transactions from parsed QFX file.

        Note: Date filtering is applied after parsing since all transactions
        are embedded in the file.

        Args:
            credentials: Dict containing file data (see fetch_accounts).
            provider_account_id: Account ID (for validation, from ProviderAccountData).
            start_date: Filter transactions after this date (inclusive).
            end_date: Filter transactions before this date (inclusive).

        Returns:
            Success(list[ProviderTransactionData]): Transactions from file.
            Failure(ProviderInvalidResponseError): If file is invalid or unparseable.
        """
        # Parse file (with caching)
        parsed_result = self._parse_file(credentials)
        if isinstance(parsed_result, Failure):
            return Failure(error=parsed_result.error)

        parsed = parsed_result.value

        # Validate account ID matches
        if parsed.account_id != provider_account_id:
            logger.warning(
                "chase_file_account_mismatch",
                provider=self.slug,
                expected=provider_account_id,
                got_masked=self._mask_account_id(parsed.account_id),
            )
            # Don't fail - user might have multiple files, just return empty
            return Success(value=[])

        # Map transactions
        transactions = self._transaction_mapper.map_transactions(
            parsed.transactions,
            currency=parsed.currency,
        )

        # Apply date filtering
        if start_date or end_date:
            transactions = self._filter_by_date(transactions, start_date, end_date)

        logger.info(
            "chase_file_fetch_transactions_succeeded",
            provider=self.slug,
            transaction_count=len(transactions),
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )

        return Success(value=transactions)

    async def fetch_holdings(
        self,
        credentials: dict[str, Any],
        provider_account_id: str,
    ) -> Result[list[ProviderHoldingData], ProviderError]:
        """Fetch holdings - not applicable for bank accounts.

        Chase checking/savings accounts don't have holdings.
        This method is required by ProviderProtocol but returns empty list.

        Args:
            credentials: Dict containing file data.
            provider_account_id: Account ID.

        Returns:
            Success([]): Always empty list (bank accounts have no holdings).
        """
        logger.debug(
            "chase_file_fetch_holdings_not_applicable",
            provider=self.slug,
        )
        return Success(value=[])

    def _parse_file(
        self,
        credentials: dict[str, Any],
    ) -> Result[ParsedAccount, ProviderError]:
        """Parse file from credentials with caching.

        Args:
            credentials: Dict containing file_content, file_format, file_name.

        Returns:
            Success(ParsedAccount): Parsed account data.
            Failure(ProviderInvalidResponseError): If file is invalid.
        """
        # Extract file content
        file_content = credentials.get("file_content")
        file_format = credentials.get("file_format", "qfx")
        file_name = credentials.get("file_name", "unknown.qfx")

        if file_content is None:
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Missing file_content in credentials",
                    provider_name=self.slug,
                )
            )

        # Ensure bytes
        if isinstance(file_content, str):
            file_content = file_content.encode("utf-8")

        # Check cache
        content_hash = hash(file_content)
        if content_hash in self._parsed_cache:
            return Success(value=self._parsed_cache[content_hash])

        # Validate format
        if file_format.lower() not in ("qfx", "ofx"):
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Unsupported file format: {file_format}",
                    provider_name=self.slug,
                )
            )

        # Parse
        result = self._parser.parse(file_content, file_name)
        if isinstance(result, Failure):
            return Failure(error=result.error)

        # Cache result
        self._parsed_cache[content_hash] = result.value

        return result

    def _filter_by_date(
        self,
        transactions: list[ProviderTransactionData],
        start_date: date | None,
        end_date: date | None,
    ) -> list[ProviderTransactionData]:
        """Filter transactions by date range.

        Args:
            transactions: List of transactions to filter.
            start_date: Include transactions on or after this date.
            end_date: Include transactions on or before this date.

        Returns:
            Filtered list of transactions.
        """
        result: list[ProviderTransactionData] = []

        for txn in transactions:
            if start_date and txn.transaction_date < start_date:
                continue
            if end_date and txn.transaction_date > end_date:
                continue
            result.append(txn)

        return result

    def _mask_account_id(self, account_id: str) -> str:
        """Mask account ID for logging."""
        if len(account_id) <= 4:
            return "****"
        return f"****{account_id[-4:]}"

    def clear_cache(self) -> None:
        """Clear the parsed file cache.

        Call this if the same provider instance processes multiple files
        and you want to free memory.
        """
        self._parsed_cache.clear()
