"""Chase account mapper.

Converts parsed QFX account data to ProviderAccountData.

Maps Chase-specific account types:
    - CHECKING → AccountType.CHECKING
    - SAVINGS → AccountType.SAVINGS

Reference:
    - OFX ACCTTYPE specification
"""

from decimal import Decimal

import structlog

from src.domain.enums.account_type import AccountType
from src.domain.protocols.provider_protocol import ProviderAccountData
from src.infrastructure.providers.chase.parsers.qfx_parser import ParsedAccount

logger = structlog.get_logger(__name__)


# Chase account type mapping
CHASE_ACCOUNT_TYPE_MAP: dict[str, str] = {
    "CHECKING": AccountType.CHECKING.value,
    "SAVINGS": AccountType.SAVINGS.value,
    "CREDITLINE": AccountType.LINE_OF_CREDIT.value,
    "MONEYMRKT": AccountType.MONEY_MARKET.value,
}


class ChaseAccountMapper:
    """Mapper for converting parsed QFX account data to ProviderAccountData.

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = ChaseAccountMapper()
        >>> parsed = parser.parse(file_bytes)
        >>> account_data = mapper.map_account(parsed.value)
    """

    def map_account(self, parsed: ParsedAccount) -> ProviderAccountData:
        """Map parsed QFX account to ProviderAccountData.

        Args:
            parsed: ParsedAccount from QFX parser.

        Returns:
            ProviderAccountData with account information.
        """
        # Map account type
        account_type = self._map_account_type(parsed.account_type)

        # Create masked account number
        masked = self._mask_account_number(parsed.account_id)

        # Generate account name
        type_label = parsed.account_type.title()
        name = f"Chase {type_label} {masked}"

        # Get balance info (default to 0 if not present)
        balance = parsed.balance.ledger_balance if parsed.balance else Decimal("0")
        available = parsed.balance.available_balance if parsed.balance else None

        return ProviderAccountData(
            provider_account_id=parsed.account_id,
            account_number_masked=masked,
            name=name,
            account_type=account_type,
            balance=balance,
            currency=parsed.currency,
            available_balance=available,
            is_active=True,  # File imports are assumed active
            raw_data={
                "bank_id": parsed.bank_id,
                "account_type_raw": parsed.account_type,
                "transaction_count": len(parsed.transactions),
            },
        )

    def _map_account_type(self, raw_type: str) -> str:
        """Map Chase account type to Dashtam account type.

        Args:
            raw_type: Account type from QFX file.

        Returns:
            Mapped AccountType value.
        """
        normalized = raw_type.upper().strip()
        mapped = CHASE_ACCOUNT_TYPE_MAP.get(normalized)

        if mapped is None:
            logger.warning(
                "chase_unknown_account_type",
                raw_type=raw_type,
                defaulting_to="other",
            )
            return AccountType.OTHER.value

        return mapped

    def _mask_account_number(self, account_id: str) -> str:
        """Mask account number for display.

        Args:
            account_id: Full account number.

        Returns:
            Masked account number like "****1234".
        """
        if len(account_id) >= 4:
            return f"****{account_id[-4:]}"
        return f"****{account_id}"
