"""Base domain event class.

This module defines the foundational DomainEvent base class used by all domain
events in the system. Domain events represent "things that happened" in the
business domain and are always named in past tense (e.g., UserRegistered,
PasswordChanged, ProviderConnected).

Architecture:
    - Frozen dataclass (immutable after creation)
    - Auto-generated event_id (UUID) for event tracking
    - Occurred_at timestamp (UTC) for event ordering
    - All events inherit from this base class

Usage:
    >>> from dataclasses import dataclass
    >>> from uuid import UUID
    >>>
    >>> @dataclass(frozen=True, kw_only=True, slots=True)
    >>> class UserRegistered(DomainEvent):
    ...     user_id: UUID
    ...     email: str
    >>>
    >>> event = UserRegistered(user_id=uuid4(), email="test@example.com")
    >>> print(event.event_id)  # Auto-generated UUID
    >>> print(event.occurred_at)  # Auto-generated timestamp

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 724-811)
    - ~/starter/clean-slate-reference.md Section 9.4 (Domain Events)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True, slots=True)
class DomainEvent:
    """Base class for all domain events.

    Domain events represent "things that happened" in the business domain.
    They are immutable records of facts that have occurred in the system.

    All domain events MUST:
        1. Inherit from this base class
        2. Use past tense naming (UserRegistered, NOT RegisterUser)
        3. Be frozen dataclasses (immutable after creation)
        4. Use kw_only=True (force keyword arguments for clarity)
        5. Include all relevant business data for event handlers

    Attributes:
        event_id: Unique identifier for this event instance. Auto-generated
            UUID v4 if not provided. Used for event tracking, deduplication,
            and correlation across distributed systems.
        occurred_at: Timestamp when the event occurred (UTC). Auto-generated
            if not provided. Used for event ordering, audit trails, and
            time-based queries.

    Example:
        >>> @dataclass(frozen=True, kw_only=True, slots=True)
        >>> class UserRegistered(DomainEvent):
        ...     '''User successfully registered in the system.'''
        ...     user_id: UUID
        ...     email: str
        ...     ip_address: str | None = None
        >>>
        >>> # Create event (event_id and occurred_at auto-generated)
        >>> event = UserRegistered(
        ...     user_id=uuid4(),
        ...     email="test@example.com",
        ...     ip_address="192.168.1.1"
        ... )
        >>>
        >>> # Access auto-generated fields
        >>> assert isinstance(event.event_id, UUID)
        >>> assert isinstance(event.occurred_at, datetime)
        >>>
        >>> # Events are immutable
        >>> # event.email = "new@example.com"  # ❌ Raises FrozenInstanceError

    Design Decisions:
        - **Frozen dataclass**: Ensures events are immutable (facts don't change)
        - **kw_only=True**: Forces keyword arguments (clarity, prevents mistakes)
        - **slots=True**: Memory optimization (Python 3.10+)
        - **Auto-generated IDs**: Simplifies event creation, ensures uniqueness
        - **UTC timestamps**: Avoids timezone confusion in distributed systems

    Notes:
        - Events should be small and focused (single responsibility)
        - Include only data relevant to event handlers (don't over-include)
        - Events are published AFTER business logic succeeds (facts, not intents)
        - For ATTEMPT events, publish BEFORE operation (e.g., LoginAttempted)
        - Event names are past tense: UserRegistered, PasswordChanged, NOT
          RegisterUser or ChangePassword
    """

    event_id: UUID = field(default_factory=uuid4)
    """Unique identifier for this event instance.

    Auto-generated UUID v4 if not provided. Used for:
        - Event tracking across systems
        - Deduplication in message queues
        - Correlation in distributed tracing
        - Audit trail linking
    """

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Timestamp when the event occurred (UTC timezone).

    Auto-generated if not provided. Used for:
        - Event ordering (temporal sequencing)
        - Audit trail timestamps
        - Time-based queries and analytics
        - Event replay ordering

    Note:
        Always in UTC to avoid timezone confusion. Event handlers should
        convert to user's local timezone if needed for display.
    """
