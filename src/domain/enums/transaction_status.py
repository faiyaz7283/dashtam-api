"""Transaction status enumeration.

Defines the lifecycle states for financial transactions.
"""

from enum import Enum


class TransactionStatus(str, Enum):
    """Transaction lifecycle status.

    Represents the current state of a transaction in its lifecycle.
    All transactions start as PENDING and typically move to SETTLED.

    **Lifecycle Flow**:
        PENDING → SETTLED (normal flow)
        PENDING → FAILED (sync/processing error)
        PENDING → CANCELLED (voided by provider)
        SETTLED → CANCELLED (rare: reversal after settlement)

    **Terminal States**: SETTLED, FAILED, CANCELLED (no further state changes)
    **Active States**: PENDING (may change state)

    **Provider Mappings**:
        - Schwab API: Maps "status" field directly
        - Plaid Transactions: Posted → SETTLED, Pending → PENDING
        - Plaid Investments: All synced transactions → SETTLED
    """

    PENDING = "pending"
    """Transaction is pending settlement.

    Common for:
    - Recent trades (T+0 to T+2 settlement period)
    - ACH transfers (1-3 business days)
    - Pending deposits/withdrawals
    - Unposted credit card transactions

    **Actions**: May still be cancelled or modified by provider
    """

    SETTLED = "settled"
    """Transaction has completed and settled.

    Characteristics:
    - Funds have cleared and are available
    - Cannot be cancelled (except rare reversals)
    - Included in account balance calculations
    - Used for historical reporting

    **Actions**: Immutable (except rare provider-initiated reversals)
    """

    FAILED = "failed"
    """Transaction failed during processing.

    Common causes:
    - Insufficient funds
    - Invalid account details
    - Provider API sync errors
    - System validation failures
    - Network timeouts during sync

    **Actions**: Terminal state, no further changes
    """

    CANCELLED = "cancelled"
    """Transaction was cancelled/voided.

    Common scenarios:
    - User-initiated cancellation (before settlement)
    - Provider-initiated reversal
    - Duplicate transaction correction
    - Fraud prevention

    **Actions**: Terminal state, no further changes
    """

    @classmethod
    def terminal_states(cls) -> list["TransactionStatus"]:
        """Return statuses that represent final states.

        Terminal states indicate the transaction will not change state again
        (except in rare reversal scenarios for SETTLED).

        Returns:
            List containing SETTLED, FAILED, and CANCELLED.

        Example:
            >>> if transaction.status in TransactionStatus.terminal_states():
            ...     # Safe to use in financial reports
        """
        return [cls.SETTLED, cls.FAILED, cls.CANCELLED]

    @classmethod
    def active_states(cls) -> list["TransactionStatus"]:
        """Return statuses that may still change.

        Active states indicate the transaction may transition to another state.

        Returns:
            List containing only PENDING.

        Example:
            >>> if transaction.status in TransactionStatus.active_states():
            ...     # Check for updates from provider
        """
        return [cls.PENDING]
