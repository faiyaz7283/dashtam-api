"""QFX/OFX file parser for Chase bank statements.

Parses QFX (Quicken Financial Exchange) files exported from Chase.
QFX is Chase's variant of OFX (Open Financial Exchange) format.

Uses the ofxparse library for SGML/XML parsing.

Architecture:
    QfxParser extracts:
    - Account information (BANKACCTFROM section)
    - Transaction list (BANKTRANLIST section)
    - Balance information (LEDGERBAL, AVAILBAL sections)

    Returns intermediate dataclasses that mappers convert to ProviderData types.

Reference:
    - OFX Specification: https://www.ofx.net/
    - ofxparse library: https://github.com/jseutter/ofxparse
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

import structlog
from ofxparse import OfxParser  # type: ignore[import-untyped]

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import ProviderError, ProviderInvalidResponseError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class ParsedTransaction:
    """Transaction extracted from QFX file.

    Intermediate representation between raw OFX and ProviderTransactionData.

    Attributes:
        fit_id: Financial Institution Transaction ID (unique per statement).
        transaction_type: OFX type (CREDIT, DEBIT, CHECK, etc.).
        date_posted: Transaction posting date.
        amount: Transaction amount (positive=credit, negative=debit).
        name: Payee/payer name.
        memo: Additional transaction details (optional).
    """

    fit_id: str
    transaction_type: str
    date_posted: date
    amount: Decimal
    name: str
    memo: str | None = None


@dataclass(frozen=True, kw_only=True)
class ParsedBalance:
    """Balance extracted from QFX file.

    Attributes:
        ledger_balance: Current ledger balance.
        available_balance: Available balance (may equal ledger).
        balance_date: Date/time balance was calculated.
        currency: ISO 4217 currency code.
    """

    ledger_balance: Decimal
    available_balance: Decimal | None
    balance_date: datetime
    currency: str


@dataclass(frozen=True, kw_only=True)
class ParsedAccount:
    """Account information extracted from QFX file.

    Attributes:
        account_id: Full account number from file.
        account_type: Account type (CHECKING, SAVINGS, etc.).
        bank_id: Bank routing number.
        currency: ISO 4217 currency code.
        transactions: List of transactions from file.
        balance: Balance information if present.
    """

    account_id: str
    account_type: str
    bank_id: str
    currency: str
    transactions: list[ParsedTransaction]
    balance: ParsedBalance | None


class QfxParser:
    """Parser for Chase QFX/OFX bank statement files.

    Extracts account, transaction, and balance data from QFX files
    exported from Chase online banking.

    Thread-safe: No mutable state, can be reused across requests.

    Example:
        >>> parser = QfxParser()
        >>> result = parser.parse(file_bytes)
        >>> match result:
        ...     case Success(parsed_account):
        ...         print(f"Found {len(parsed_account.transactions)} transactions")
        ...     case Failure(error):
        ...         print(f"Parse failed: {error.message}")
    """

    def parse(
        self,
        file_content: bytes,
        file_name: str = "unknown.qfx",
    ) -> Result[ParsedAccount, ProviderError]:
        """Parse QFX file content into structured data.

        Args:
            file_content: Raw bytes of QFX file.
            file_name: Original filename for logging/debugging.

        Returns:
            Success(ParsedAccount): Parsed account with transactions and balance.
            Failure(ProviderInvalidResponseError): If file is invalid or unparseable.
        """
        logger.info(
            "qfx_parse_started",
            file_name=file_name,
            file_size=len(file_content),
        )

        try:
            # ofxparse expects a file-like object
            file_handle = BytesIO(file_content)
            ofx = OfxParser.parse(file_handle)
        except Exception as e:
            logger.error(
                "qfx_parse_failed",
                file_name=file_name,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Failed to parse QFX file: {e}",
                    provider_name="chase_file",
                )
            )

        # OFX files can contain multiple accounts, but Chase exports one per file
        if not ofx.accounts:
            logger.warning(
                "qfx_parse_no_accounts",
                file_name=file_name,
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="QFX file contains no account data",
                    provider_name="chase_file",
                )
            )

        # Chase exports one account per file
        account = ofx.accounts[0]

        # Extract account info
        account_id = str(account.account_id) if account.account_id else ""
        account_type = (
            str(account.account_type).upper() if account.account_type else "UNKNOWN"
        )
        bank_id = str(account.routing_number) if account.routing_number else ""
        currency = (
            str(account.curdef)
            if hasattr(account, "curdef") and account.curdef
            else "USD"
        )

        # Parse transactions
        transactions = self._parse_transactions(account, file_name)

        # Parse balance
        balance = self._parse_balance(account, currency)

        parsed = ParsedAccount(
            account_id=account_id,
            account_type=account_type,
            bank_id=bank_id,
            currency=currency,
            transactions=transactions,
            balance=balance,
        )

        logger.info(
            "qfx_parse_succeeded",
            file_name=file_name,
            account_id=self._mask_account_id(account_id),
            account_type=account_type,
            transaction_count=len(transactions),
            has_balance=balance is not None,
        )

        return Success(value=parsed)

    def _parse_transactions(
        self,
        account: Any,
        file_name: str,
    ) -> list[ParsedTransaction]:
        """Extract transactions from OFX account object.

        Args:
            account: ofxparse Account object.
            file_name: For logging.

        Returns:
            List of parsed transactions.
        """
        transactions: list[ParsedTransaction] = []

        statement = account.statement
        if not statement or not statement.transactions:
            return transactions

        for txn in statement.transactions:
            try:
                # Extract required fields
                fit_id = str(txn.id) if txn.id else ""
                txn_type = str(txn.type).upper() if txn.type else "OTHER"

                # Parse date - ofxparse returns datetime
                if isinstance(txn.date, datetime):
                    date_posted = txn.date.date()
                elif isinstance(txn.date, date):
                    date_posted = txn.date
                else:
                    # Skip transactions without valid date
                    logger.warning(
                        "qfx_transaction_invalid_date",
                        file_name=file_name,
                        fit_id=fit_id,
                    )
                    continue

                # Parse amount - ofxparse returns Decimal
                amount = (
                    Decimal(str(txn.amount)) if txn.amount is not None else Decimal("0")
                )

                # Extract name and memo
                name = str(txn.payee) if txn.payee else ""
                memo = str(txn.memo) if txn.memo else None

                parsed_txn = ParsedTransaction(
                    fit_id=fit_id,
                    transaction_type=txn_type,
                    date_posted=date_posted,
                    amount=amount,
                    name=name,
                    memo=memo,
                )
                transactions.append(parsed_txn)

            except Exception as e:
                # Log but continue - don't fail entire parse for one bad transaction
                logger.warning(
                    "qfx_transaction_parse_error",
                    file_name=file_name,
                    error=str(e),
                )
                continue

        return transactions

    def _parse_balance(
        self,
        account: Any,
        currency: str,
    ) -> ParsedBalance | None:
        """Extract balance information from OFX account object.

        Args:
            account: ofxparse Account object.
            currency: Currency code from account.

        Returns:
            ParsedBalance if balance data present, None otherwise.
        """
        statement = account.statement
        if not statement:
            return None

        # ofxparse exposes balance and available_balance
        ledger_balance = getattr(statement, "balance", None)
        available_balance = getattr(statement, "available_balance", None)
        balance_date = getattr(statement, "balance_date", None)

        if ledger_balance is None:
            return None

        # Convert to Decimal
        ledger = Decimal(str(ledger_balance))
        available = (
            Decimal(str(available_balance)) if available_balance is not None else None
        )

        # Default to now if no balance date
        if balance_date is None:
            balance_date = datetime.now()
        elif isinstance(balance_date, date) and not isinstance(balance_date, datetime):
            balance_date = datetime.combine(balance_date, datetime.min.time())

        return ParsedBalance(
            ledger_balance=ledger,
            available_balance=available,
            balance_date=balance_date,
            currency=currency,
        )

    def _mask_account_id(self, account_id: str) -> str:
        """Mask account ID for logging (show last 4 digits only).

        Args:
            account_id: Full account number.

        Returns:
            Masked account number like "****1234".
        """
        if len(account_id) <= 4:
            return "****"
        return f"****{account_id[-4:]}"
