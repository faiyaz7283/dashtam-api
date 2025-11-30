"""Immutable Money value object with Decimal precision.

Financial calculations require exact precision - floats introduce rounding
errors that accumulate in financial systems. This module provides a Money
value object using Python's Decimal type.

Error Handling:
    Arithmetic operations between different currencies raise CurrencyMismatchError
    (a ValueError subclass). This follows Python's convention for type-incompatible
    operations (e.g., str + int raises TypeError). This is compliant with our error
    handling architecture - see "Value Object Arithmetic Exceptions" section in
    docs/architecture/error-handling-architecture.md for rationale.

Reference:
    - docs/architecture/account-domain-model.md
    - docs/architecture/error-handling-architecture.md

Usage:
    from decimal import Decimal
    from src.domain.value_objects import Money

    balance = Money(Decimal("1000.00"), "USD")
    fee = Money(Decimal("9.99"), "USD")
    result = balance - fee  # Money(990.01, USD)
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Self


# ISO 4217 currency codes - common currencies supported
# Expand as needed for international accounts
VALID_CURRENCIES: frozenset[str] = frozenset(
    {
        # Major currencies
        "USD",  # US Dollar
        "EUR",  # Euro
        "GBP",  # British Pound
        "JPY",  # Japanese Yen
        "CHF",  # Swiss Franc
        "CAD",  # Canadian Dollar
        "AUD",  # Australian Dollar
        "NZD",  # New Zealand Dollar
        # Asian currencies
        "CNY",  # Chinese Yuan
        "HKD",  # Hong Kong Dollar
        "SGD",  # Singapore Dollar
        "KRW",  # South Korean Won
        "INR",  # Indian Rupee
        "TWD",  # Taiwan Dollar
        # European currencies
        "SEK",  # Swedish Krona
        "NOK",  # Norwegian Krone
        "DKK",  # Danish Krone
        "PLN",  # Polish Zloty
        "CZK",  # Czech Koruna
        # Americas
        "MXN",  # Mexican Peso
        "BRL",  # Brazilian Real
        # Other
        "ZAR",  # South African Rand
        "RUB",  # Russian Ruble
        "TRY",  # Turkish Lira
    }
)


class CurrencyMismatchError(ValueError):
    """Raised when attempting operations on different currencies."""

    def __init__(self, currency1: str, currency2: str) -> None:
        """Initialize currency mismatch error.

        Args:
            currency1: First currency code.
            currency2: Second currency code.
        """
        super().__init__(
            f"Cannot perform operation between {currency1} and {currency2}"
        )
        self.currency1 = currency1
        self.currency2 = currency2


def validate_currency(code: str) -> str:
    """Validate and normalize currency code.

    Args:
        code: Currency code (case-insensitive).

    Returns:
        Uppercase ISO 4217 currency code.

    Raises:
        ValueError: If code is not a valid ISO 4217 currency.

    Example:
        >>> validate_currency("usd")
        'USD'
        >>> validate_currency("XYZ")
        ValueError: Invalid currency code: XYZ
    """
    if not code or not isinstance(code, str):
        raise ValueError("Currency code cannot be empty")

    normalized = code.upper().strip()

    if len(normalized) != 3:
        raise ValueError(f"Currency code must be 3 characters: {code}")

    if normalized not in VALID_CURRENCIES:
        raise ValueError(f"Invalid currency code: {code}")

    return normalized


@dataclass(frozen=True)
class Money:
    """Immutable monetary value with currency.

    Financial calculations require exact precision - floats introduce
    rounding errors that accumulate in financial systems. This class
    uses Python's Decimal for exact decimal arithmetic.

    Attributes:
        amount: Decimal value (positive, negative, or zero).
        currency: ISO 4217 currency code (e.g., "USD", "EUR").

    Immutability:
        Frozen dataclass ensures Money cannot be modified after creation.
        All arithmetic operations return new Money instances.

    Currency Safety:
        Operations between different currencies raise CurrencyMismatchError.
        This prevents accidental mixing of currencies without conversion.

    Example:
        >>> from decimal import Decimal
        >>> balance = Money(Decimal("1000.00"), "USD")
        >>> fee = Money(Decimal("9.99"), "USD")
        >>> balance - fee
        Money(amount=Decimal('990.01'), currency='USD')

    Warning:
        Always use string initialization for Decimal to avoid float precision:
        >>> Money(Decimal("0.1"), "USD")  # Correct
        >>> Money(Decimal(0.1), "USD")    # Wrong - already imprecise!
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        """Validate money after initialization.

        Raises:
            ValueError: If amount is not a valid Decimal or currency is invalid.
        """
        # Validate amount is Decimal
        if not isinstance(self.amount, Decimal):
            try:
                # Allow int/float but convert to Decimal
                object.__setattr__(self, "amount", Decimal(str(self.amount)))
            except (InvalidOperation, TypeError) as e:
                raise ValueError(f"Amount must be a valid number: {e}") from e

        # Check for special values (NaN, Infinity)
        if self.amount.is_nan() or self.amount.is_infinite():
            raise ValueError("Amount cannot be NaN or Infinite")

        # Validate and normalize currency
        validated_currency = validate_currency(self.currency)
        object.__setattr__(self, "currency", validated_currency)

    # -------------------------------------------------------------------------
    # Arithmetic Operations (Same Currency Only)
    # -------------------------------------------------------------------------

    def __add__(self, other: "Money") -> "Money":
        """Add two Money values.

        Args:
            other: Money to add.

        Returns:
            New Money with sum of amounts.

        Raises:
            CurrencyMismatchError: If currencies differ.
            TypeError: If other is not Money.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract two Money values.

        Args:
            other: Money to subtract.

        Returns:
            New Money with difference of amounts.

        Raises:
            CurrencyMismatchError: If currencies differ.
            TypeError: If other is not Money.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, scalar: Decimal | int | float) -> "Money":
        """Multiply Money by a scalar.

        Args:
            scalar: Number to multiply by.

        Returns:
            New Money with scaled amount.

        Example:
            >>> balance = Money(Decimal("100.00"), "USD")
            >>> balance * 2
            Money(amount=Decimal('200.00'), currency='USD')
        """
        if isinstance(scalar, (Decimal, int, float)):
            return Money(self.amount * Decimal(str(scalar)), self.currency)
        return NotImplemented

    def __rmul__(self, scalar: Decimal | int | float) -> "Money":
        """Right multiply (scalar * Money).

        Args:
            scalar: Number to multiply by.

        Returns:
            New Money with scaled amount.
        """
        return self.__mul__(scalar)

    def __neg__(self) -> "Money":
        """Negate the amount.

        Returns:
            New Money with negated amount.

        Example:
            >>> debt = Money(Decimal("100.00"), "USD")
            >>> -debt
            Money(amount=Decimal('-100.00'), currency='USD')
        """
        return Money(-self.amount, self.currency)

    def __abs__(self) -> "Money":
        """Get absolute value.

        Returns:
            New Money with absolute amount.
        """
        return Money(abs(self.amount), self.currency)

    # -------------------------------------------------------------------------
    # Comparison Operations (Same Currency Only)
    # -------------------------------------------------------------------------

    def __lt__(self, other: "Money") -> bool:
        """Less than comparison.

        Args:
            other: Money to compare.

        Returns:
            True if this amount is less than other.

        Raises:
            CurrencyMismatchError: If currencies differ.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        """Less than or equal comparison.

        Args:
            other: Money to compare.

        Returns:
            True if this amount is less than or equal to other.

        Raises:
            CurrencyMismatchError: If currencies differ.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        """Greater than comparison.

        Args:
            other: Money to compare.

        Returns:
            True if this amount is greater than other.

        Raises:
            CurrencyMismatchError: If currencies differ.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        """Greater than or equal comparison.

        Args:
            other: Money to compare.

        Returns:
            True if this amount is greater than or equal to other.

        Raises:
            CurrencyMismatchError: If currencies differ.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.amount >= other.amount

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def is_positive(self) -> bool:
        """Check if amount is positive (> 0).

        Returns:
            True if amount is greater than zero.
        """
        return self.amount > 0

    def is_negative(self) -> bool:
        """Check if amount is negative (< 0).

        Returns:
            True if amount is less than zero.
        """
        return self.amount < 0

    def is_zero(self) -> bool:
        """Check if amount is zero.

        Returns:
            True if amount equals zero.
        """
        return self.amount == 0

    # -------------------------------------------------------------------------
    # Factory Methods
    # -------------------------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = "USD") -> Self:
        """Create Money with zero amount.

        Args:
            currency: Currency code (default: USD).

        Returns:
            Money with zero amount in specified currency.

        Example:
            >>> Money.zero("EUR")
            Money(amount=Decimal('0'), currency='EUR')
        """
        return cls(Decimal("0"), currency)

    @classmethod
    def from_cents(cls, cents: int, currency: str = "USD") -> Self:
        """Create Money from cents (or smallest unit).

        Useful for APIs that return amounts in cents.

        Args:
            cents: Amount in cents/smallest currency unit.
            currency: Currency code (default: USD).

        Returns:
            Money with converted amount.

        Example:
            >>> Money.from_cents(12345, "USD")
            Money(amount=Decimal('123.45'), currency='USD')

        Note:
            Assumes 100 cents per unit. For currencies with different
            subdivisions (e.g., JPY has no cents), use direct construction.
        """
        return cls(Decimal(cents) / Decimal("100"), currency)

    # -------------------------------------------------------------------------
    # String Representations
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        """Return repr for debugging.

        Returns:
            Detailed string representation.
        """
        return f"Money(amount={self.amount!r}, currency={self.currency!r})"

    def __str__(self) -> str:
        """Return human-readable string.

        Returns:
            Formatted string like "1,234.56 USD".
        """
        # Format with 2 decimal places and thousands separator
        formatted = f"{self.amount:,.2f}"
        return f"{formatted} {self.currency}"

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _check_same_currency(self, other: "Money") -> None:
        """Verify currencies match for operations.

        Args:
            other: Other Money to check.

        Raises:
            CurrencyMismatchError: If currencies differ.
        """
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency)
