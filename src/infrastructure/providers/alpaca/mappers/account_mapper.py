"""Alpaca account mapper.

Converts Alpaca Trading API account JSON responses to ProviderAccountData.
Contains Alpaca-specific knowledge about JSON structure.

Alpaca Account Response Structure:
    {
        "id": "ba0d71b6-1044-4334-9643-ebbf8e2fcbf9",
        "account_number": "PA3CRCJ7QUIR",
        "status": "ACTIVE",
        "currency": "USD",
        "buying_power": "200000",
        "cash": "100000",
        "equity": "100000",
        ...
    }

Reference:
    - https://docs.alpaca.markets/reference/getaccount-1
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.enums.account_type import AccountType
from src.domain.protocols.provider_protocol import ProviderAccountData

logger = structlog.get_logger(__name__)


class AlpacaAccountMapper:
    """Mapper for converting Alpaca account data to ProviderAccountData.

    This mapper handles:
    - Extracting data from Alpaca's account JSON structure
    - Converting balance values to Decimal with proper precision
    - Masking account numbers for security
    - Determining account type (Alpaca only has brokerage accounts)

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = AlpacaAccountMapper()
        >>> alpaca_data = {"account_number": "PA123", "equity": "100000", ...}
        >>> result = mapper.map_account(alpaca_data)
        >>> if result is not None:
        ...     print(f"Account: {result.name}")
    """

    def map_account(self, data: dict[str, Any]) -> ProviderAccountData | None:
        """Map Alpaca account JSON to ProviderAccountData.

        Args:
            data: Account object from Alpaca API response.

        Returns:
            ProviderAccountData if mapping succeeds, None if data is invalid
            or missing required fields.

        Example:
            >>> data = {
            ...     "account_number": "PA3CRCJ7QUIR",
            ...     "status": "ACTIVE",
            ...     "equity": "100000",
            ...     "buying_power": "200000",
            ... }
            >>> result = mapper.map_account(data)
            >>> result.provider_account_id
            'PA3CRCJ7QUIR'
        """
        try:
            return self._map_account_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError) as e:
            logger.warning(
                "alpaca_account_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _map_account_internal(self, data: dict[str, Any]) -> ProviderAccountData | None:
        """Internal mapping logic.

        Raises exceptions on invalid data (caught by map_account).
        """
        # Extract account number (required)
        account_number = data.get("account_number", "")
        if not account_number:
            logger.debug("alpaca_account_missing_account_number")
            return None

        # Get status
        status = data.get("status", "UNKNOWN")
        is_active = status == "ACTIVE"

        # Parse balance values (Alpaca returns strings)
        equity = self._parse_decimal(data.get("equity", "0"))
        buying_power = self._parse_decimal(data.get("buying_power"))
        cash = self._parse_decimal(data.get("cash"))

        # Currency (Alpaca only supports USD)
        currency = data.get("currency", "USD")

        # Generate masked account number
        masked = self._mask_account_number(account_number)

        # Generate account name
        # Alpaca doesn't have account names, so we generate one
        account_type_label = "Paper" if account_number.startswith("PA") else "Live"
        name = f"Alpaca {account_type_label} {masked}"

        return ProviderAccountData(
            provider_account_id=account_number,
            account_number_masked=masked,
            name=name,
            account_type=AccountType.BROKERAGE.value,  # Alpaca only has brokerage
            balance=equity,
            currency=currency,
            available_balance=buying_power if buying_power else cash,
            is_active=is_active,
            raw_data=data,
        )

    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse numeric value to Decimal with proper precision.

        Args:
            value: Numeric value (int, float, str, or None).

        Returns:
            Decimal representation, Decimal("0") for None/invalid.
        """
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            logger.warning(
                "alpaca_invalid_decimal_value",
                value=value,
                value_type=type(value).__name__,
            )
            return Decimal("0")

    def _mask_account_number(self, account_number: str) -> str:
        """Mask account number for display, showing only last 4 characters.

        Args:
            account_number: Full account number from Alpaca.

        Returns:
            Masked string like "****QUIR".
        """
        if len(account_number) >= 4:
            return f"****{account_number[-4:]}"
        return f"****{account_number}"
