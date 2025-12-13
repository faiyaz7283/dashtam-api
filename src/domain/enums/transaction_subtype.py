"""Transaction subtype enumeration.

This module defines the specific transaction action classification.
Part of the two-level classification system (Type + Subtype).
"""

from enum import Enum


class TransactionSubtype(str, Enum):
    """Specific transaction action within a type.

    Subtypes provide granular detail while types provide broad categories.
    Not all subtypes are valid for all types - see valid combinations in
    architecture documentation.

    Asset Class Note
    ----------------
    Securities can be stocks, ETFs, options, futures, mutual funds, bonds, etc.
    The subtype does NOT specify asset class - that's captured in:
    - asset_type field (EQUITY, OPTION, MUTUAL_FUND, FIXED_INCOME, etc.)
    - symbol field (AAPL, AAPL230120C00150000 for options, etc.)

    For options specifically:
    - BUY/SELL = opening or closing positions
    - EXERCISE = exercising an option contract
    - ASSIGNMENT = being assigned on a short option
    - EXPIRATION = option expired worthless
    """

    # TRADE subtypes (executed security transactions)
    BUY = "buy"  # Purchase security (long)
    SELL = "sell"  # Sell security (close long)
    SHORT_SELL = "short_sell"  # Short sale (open short)
    BUY_TO_COVER = "buy_to_cover"  # Cover short position

    # TRADE subtypes - options/derivatives specific
    EXERCISE = "exercise"  # Exercise option contract
    ASSIGNMENT = "assignment"  # Assigned on short option
    EXPIRATION = "expiration"  # Option expired

    # TRANSFER subtypes (cash movements)
    DEPOSIT = "deposit"  # Cash deposited (ACH, check, etc.)
    WITHDRAWAL = "withdrawal"  # Cash withdrawn
    WIRE_IN = "wire_in"  # Incoming wire transfer
    WIRE_OUT = "wire_out"  # Outgoing wire transfer
    TRANSFER_IN = "transfer_in"  # Security/cash transferred in
    TRANSFER_OUT = "transfer_out"  # Security/cash transferred out
    INTERNAL = "internal"  # Internal account transfer

    # INCOME subtypes (passive income)
    DIVIDEND = "dividend"  # Stock/fund dividend
    INTEREST = "interest"  # Interest earned
    CAPITAL_GAIN = "capital_gain"  # Capital gain distribution
    DISTRIBUTION = "distribution"  # Other distribution

    # FEE subtypes
    COMMISSION = "commission"  # Trading commission
    ACCOUNT_FEE = "account_fee"  # Account maintenance fee
    MARGIN_INTEREST = "margin_interest"  # Margin interest charged
    OTHER_FEE = "other_fee"  # Other fees

    # OTHER subtypes
    ADJUSTMENT = "adjustment"  # Balance adjustment
    JOURNAL = "journal"  # Journal entry
    UNKNOWN = "unknown"  # Unmapped/unknown

    @classmethod
    def trade_subtypes(cls) -> list["TransactionSubtype"]:
        """Return subtypes for TRADE transactions.

        Returns:
            List of subtypes valid for TRADE type transactions.

        Examples:
            >>> TransactionSubtype.trade_subtypes()
            [TransactionSubtype.BUY, TransactionSubtype.SELL, ...]
        """
        return [
            cls.BUY,
            cls.SELL,
            cls.SHORT_SELL,
            cls.BUY_TO_COVER,
            cls.EXERCISE,
            cls.ASSIGNMENT,
            cls.EXPIRATION,
        ]

    @classmethod
    def transfer_subtypes(cls) -> list["TransactionSubtype"]:
        """Return subtypes for TRANSFER transactions.

        Returns:
            List of subtypes valid for TRANSFER type transactions.

        Examples:
            >>> TransactionSubtype.transfer_subtypes()
            [TransactionSubtype.DEPOSIT, TransactionSubtype.WITHDRAWAL, ...]
        """
        return [
            cls.DEPOSIT,
            cls.WITHDRAWAL,
            cls.WIRE_IN,
            cls.WIRE_OUT,
            cls.TRANSFER_IN,
            cls.TRANSFER_OUT,
            cls.INTERNAL,
        ]

    @classmethod
    def income_subtypes(cls) -> list["TransactionSubtype"]:
        """Return subtypes for INCOME transactions.

        Returns:
            List of subtypes valid for INCOME type transactions.

        Examples:
            >>> TransactionSubtype.income_subtypes()
            [TransactionSubtype.DIVIDEND, TransactionSubtype.INTEREST, ...]
        """
        return [
            cls.DIVIDEND,
            cls.INTEREST,
            cls.CAPITAL_GAIN,
            cls.DISTRIBUTION,
        ]

    @classmethod
    def fee_subtypes(cls) -> list["TransactionSubtype"]:
        """Return subtypes for FEE transactions.

        Returns:
            List of subtypes valid for FEE type transactions.

        Examples:
            >>> TransactionSubtype.fee_subtypes()
            [TransactionSubtype.COMMISSION, TransactionSubtype.ACCOUNT_FEE, ...]
        """
        return [
            cls.COMMISSION,
            cls.ACCOUNT_FEE,
            cls.MARGIN_INTEREST,
            cls.OTHER_FEE,
        ]
