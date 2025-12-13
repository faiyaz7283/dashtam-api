"""Schwab account mapper.

Converts Schwab Trader API account JSON responses to ProviderAccountData.
Contains Schwab-specific knowledge about JSON structure and type mappings.

Schwab Account Response Structure:
    [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "12345678",
                "accountName": "My Brokerage",
                "currentBalances": {
                    "liquidationValue": 50000.00,
                    "availableFunds": 10000.00,
                    "cashBalance": 10000.00
                }
            }
        }
    ]

Reference:
    - docs/architecture/provider-integration-architecture.md
    - Schwab Trader API: https://developer.schwab.com
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.enums.account_type import AccountType
from src.domain.protocols.provider_protocol import ProviderAccountData

logger = structlog.get_logger(__name__)


# =============================================================================
# Account Type Mapping
# =============================================================================

# Schwab account type → Dashtam AccountType
# Based on Schwab Trader API documentation
SCHWAB_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
    # Brokerage accounts
    "CASH": AccountType.BROKERAGE,
    "MARGIN": AccountType.BROKERAGE,
    "INDIVIDUAL": AccountType.BROKERAGE,
    "JOINT": AccountType.BROKERAGE,
    # Retirement accounts
    "IRA": AccountType.IRA,
    "ROTH_IRA": AccountType.ROTH_IRA,
    "ROTH": AccountType.ROTH_IRA,
    "TRADITIONAL_IRA": AccountType.IRA,
    "ROLLOVER_IRA": AccountType.IRA,
    "SEP_IRA": AccountType.IRA,
    "SIMPLE_IRA": AccountType.IRA,
    # 401k types
    "401K": AccountType.RETIREMENT_401K,
    "ROTH_401K": AccountType.RETIREMENT_401K,
    # Other retirement
    "403B": AccountType.RETIREMENT_403B,
    # HSA
    "HSA": AccountType.HSA,
    # Trust accounts (map to brokerage)
    "TRUST": AccountType.BROKERAGE,
    "CUSTODIAL": AccountType.BROKERAGE,
    # Education accounts
    "529": AccountType.OTHER,
    "COVERDELL": AccountType.OTHER,
    # Corporate accounts
    "CORPORATE": AccountType.BROKERAGE,
    "LLC": AccountType.BROKERAGE,
    "PARTNERSHIP": AccountType.BROKERAGE,
}


class SchwabAccountMapper:
    """Mapper for converting Schwab account data to ProviderAccountData.

    This mapper handles:
    - Extracting data from Schwab's nested JSON structure
    - Mapping Schwab account types to Dashtam AccountType enum
    - Converting balance values to Decimal with proper precision
    - Masking account numbers for security

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = SchwabAccountMapper()
        >>> schwab_data = {"securitiesAccount": {...}}
        >>> result = mapper.map_account(schwab_data)
        >>> if result is not None:
        ...     print(f"Account: {result.name}")
    """

    def map_account(self, data: dict[str, Any]) -> ProviderAccountData | None:
        """Map single Schwab account JSON to ProviderAccountData.

        Args:
            data: Single account object from Schwab API response.
                Expected structure: {"securitiesAccount": {...}}

        Returns:
            ProviderAccountData if mapping succeeds, None if data is invalid
            or missing required fields.

        Example:
            >>> data = {
            ...     "securitiesAccount": {
            ...         "type": "INDIVIDUAL",
            ...         "accountNumber": "12345678",
            ...         "currentBalances": {"liquidationValue": 50000}
            ...     }
            ... }
            >>> result = mapper.map_account(data)
            >>> result.provider_account_id
            '12345678'
        """
        try:
            return self._map_account_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError) as e:
            logger.warning(
                "schwab_account_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def map_accounts(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderAccountData]:
        """Map list of Schwab account JSON objects to ProviderAccountData.

        Skips invalid accounts and logs warnings. Never raises exceptions.

        Args:
            data_list: List of account objects from Schwab API.

        Returns:
            List of successfully mapped accounts. May be empty if all fail.

        Example:
            >>> accounts = mapper.map_accounts(schwab_response)
            >>> print(f"Mapped {len(accounts)} accounts")
        """
        accounts: list[ProviderAccountData] = []

        for data in data_list:
            account = self.map_account(data)
            if account is not None:
                accounts.append(account)

        return accounts

    def _map_account_internal(self, data: dict[str, Any]) -> ProviderAccountData | None:
        """Internal mapping logic.

        Raises exceptions on invalid data (caught by map_account).
        """
        # Schwab wraps account data in "securitiesAccount" key
        securities_account = data.get("securitiesAccount")
        if not securities_account:
            logger.debug(
                "schwab_account_missing_securities_account",
                keys=list(data.keys()) if isinstance(data, dict) else None,
            )
            return None

        # Extract required fields
        account_number = securities_account.get("accountNumber", "")
        if not account_number:
            logger.debug("schwab_account_missing_account_number")
            return None

        # Get balances
        current_balances = securities_account.get("currentBalances", {})

        # Map account type
        schwab_type = securities_account.get("type", "UNKNOWN")
        account_type = self._map_account_type(schwab_type)

        # Parse balance values
        balance = self._parse_decimal(current_balances.get("liquidationValue", 0))
        available_balance = self._parse_decimal(
            current_balances.get("availableFunds")
            or current_balances.get("cashBalance")
        )

        # Generate masked account number
        masked = self._mask_account_number(account_number)

        # Get account name (fallback to masked number)
        name = (
            securities_account.get("accountName")
            or securities_account.get("nickname")
            or f"Schwab {masked}"
        )

        return ProviderAccountData(
            provider_account_id=account_number,
            account_number_masked=masked,
            name=name,
            account_type=account_type.value,
            balance=balance,
            currency="USD",  # Schwab accounts are USD
            available_balance=available_balance if available_balance else None,
            is_active=True,
            raw_data=data,
        )

    def _map_account_type(self, schwab_type: str) -> AccountType:
        """Map Schwab account type string to AccountType enum.

        Args:
            schwab_type: Account type from Schwab API (e.g., "INDIVIDUAL", "IRA").

        Returns:
            Mapped AccountType, defaults to OTHER for unknown types.

        Example:
            >>> mapper._map_account_type("ROTH_IRA")
            AccountType.ROTH_IRA
            >>> mapper._map_account_type("UNKNOWN_TYPE")
            AccountType.OTHER
        """
        # Normalize to uppercase for matching
        normalized = schwab_type.upper().strip()

        account_type = SCHWAB_ACCOUNT_TYPE_MAP.get(normalized)

        if account_type is None:
            logger.info(
                "schwab_unknown_account_type",
                schwab_type=schwab_type,
                defaulting_to="OTHER",
            )
            return AccountType.OTHER

        return account_type

    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse numeric value to Decimal with proper precision.

        Args:
            value: Numeric value (int, float, str, or None).

        Returns:
            Decimal representation, Decimal("0") for None/invalid.

        Example:
            >>> mapper._parse_decimal(50000.50)
            Decimal('50000.50')
            >>> mapper._parse_decimal(None)
            Decimal('0')
        """
        if value is None:
            return Decimal("0")

        try:
            # Convert to string first to preserve precision
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            logger.warning(
                "schwab_invalid_decimal_value",
                value=value,
                value_type=type(value).__name__,
            )
            return Decimal("0")

    def _mask_account_number(self, account_number: str) -> str:
        """Mask account number for display, showing only last 4 digits.

        Args:
            account_number: Full account number from Schwab.

        Returns:
            Masked string like "****1234".

        Example:
            >>> mapper._mask_account_number("12345678")
            '****5678'
            >>> mapper._mask_account_number("123")
            '****123'
        """
        if len(account_number) >= 4:
            return f"****{account_number[-4:]}"
        return f"****{account_number}"
