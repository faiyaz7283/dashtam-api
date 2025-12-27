"""Chase transaction mapper.

Converts parsed QFX transaction data to ProviderTransactionData.

OFX Transaction Types (TRNTYPE):
    - CREDIT: Credit (deposit, interest, refund)
    - DEBIT: Debit (withdrawal, payment, fee)
    - CHECK: Check
    - INT: Interest
    - DIV: Dividend
    - FEE: Fee
    - SRVCHG: Service charge
    - DEP: Deposit
    - ATM: ATM transaction
    - POS: Point of sale
    - XFER: Transfer
    - PAYMENT: Payment
    - DIRECTDEP: Direct deposit
    - DIRECTDEBIT: Direct debit
    - REPEATPMT: Repeating payment
    - OTHER: Other

Reference:
    - OFX TRNTYPE specification
"""

import structlog

from src.domain.protocols.provider_protocol import ProviderTransactionData
from src.infrastructure.providers.chase.parsers.qfx_parser import ParsedTransaction

logger = structlog.get_logger(__name__)


# OFX transaction type → Dashtam transaction type
OFX_TRANSACTION_TYPE_MAP: dict[str, str] = {
    # Credit types
    "CREDIT": "deposit",
    "DEP": "deposit",
    "DIRECTDEP": "deposit",
    "INT": "income",
    "DIV": "income",
    # Debit types
    "DEBIT": "withdrawal",
    "CHECK": "check",
    "ATM": "withdrawal",
    "POS": "purchase",
    "PAYMENT": "payment",
    "DIRECTDEBIT": "payment",
    "REPEATPMT": "payment",
    # Fee types
    "FEE": "fee",
    "SRVCHG": "fee",
    # Transfer types
    "XFER": "transfer",
    # Other
    "OTHER": "other",
}

# Transaction subtype mapping based on name patterns
NAME_SUBTYPE_PATTERNS: dict[str, str] = {
    "ZELLE": "zelle",
    "VENMO": "venmo",
    "PAYPAL": "paypal",
    "ACH": "ach",
    "WIRE": "wire",
    "TRANSFER": "internal_transfer",
    "ATM": "atm",
    "CHECK": "check",
    "AUTOPAY": "autopay",
    "DIRECT DEPOSIT": "direct_deposit",
    "PAYROLL": "payroll",
    "INTEREST": "interest",
}


class ChaseTransactionMapper:
    """Mapper for converting parsed QFX transaction data to ProviderTransactionData.

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = ChaseTransactionMapper()
        >>> transactions = mapper.map_transactions(parsed.transactions)
    """

    def map_transaction(
        self,
        parsed: ParsedTransaction,
        currency: str = "USD",
    ) -> ProviderTransactionData:
        """Map single parsed transaction to ProviderTransactionData.

        Args:
            parsed: ParsedTransaction from QFX parser.
            currency: Currency code (from account).

        Returns:
            ProviderTransactionData with transaction information.
        """
        # Map transaction type
        transaction_type = self._map_transaction_type(parsed.transaction_type)

        # Determine subtype from name/memo
        subtype = self._detect_subtype(parsed.name, parsed.memo)

        # Build description (combine name and memo)
        description = self._build_description(parsed.name, parsed.memo)

        # Determine status (QFX transactions are always posted)
        status = "posted"

        return ProviderTransactionData(
            provider_transaction_id=parsed.fit_id,
            transaction_type=transaction_type,
            subtype=subtype,
            amount=parsed.amount,
            currency=currency,
            description=description,
            transaction_date=parsed.date_posted,
            status=status,
            raw_data={
                "fit_id": parsed.fit_id,
                "trntype": parsed.transaction_type,
                "name": parsed.name,
                "memo": parsed.memo,
            },
        )

    def map_transactions(
        self,
        transactions: list[ParsedTransaction],
        currency: str = "USD",
    ) -> list[ProviderTransactionData]:
        """Map list of parsed transactions to ProviderTransactionData.

        Args:
            transactions: List of ParsedTransaction from QFX parser.
            currency: Currency code (from account).

        Returns:
            List of ProviderTransactionData.
        """
        result: list[ProviderTransactionData] = []

        for txn in transactions:
            mapped = self.map_transaction(txn, currency)
            result.append(mapped)

        return result

    def _map_transaction_type(self, raw_type: str) -> str:
        """Map OFX transaction type to Dashtam transaction type.

        Args:
            raw_type: TRNTYPE from QFX file.

        Returns:
            Mapped transaction type.
        """
        normalized = raw_type.upper().strip()
        mapped = OFX_TRANSACTION_TYPE_MAP.get(normalized)

        if mapped is None:
            logger.info(
                "chase_unknown_transaction_type",
                raw_type=raw_type,
                defaulting_to="other",
            )
            return "other"

        return mapped

    def _detect_subtype(
        self,
        name: str,
        memo: str | None,
    ) -> str | None:
        """Detect transaction subtype from name and memo fields.

        Args:
            name: Transaction name (payee).
            memo: Transaction memo (optional).

        Returns:
            Detected subtype or None.
        """
        # Combine name and memo for pattern matching
        combined = f"{name} {memo or ''}".upper()

        for pattern, subtype in NAME_SUBTYPE_PATTERNS.items():
            if pattern in combined:
                return subtype

        return None

    def _build_description(
        self,
        name: str,
        memo: str | None,
    ) -> str:
        """Build transaction description from name and memo.

        Args:
            name: Transaction name (payee).
            memo: Transaction memo (optional).

        Returns:
            Combined description string.
        """
        if memo:
            return f"{name} - {memo}"
        return name
