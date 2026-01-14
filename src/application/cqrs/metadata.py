"""CQRS Metadata Types.

Dataclasses and enums for CQRS registry metadata.
These types define the structure of command and query registry entries.

Design Principles:
- Immutable (frozen=True) - registry entries never change at runtime
- Type-safe (kw_only=True) - explicit field assignment
- Self-documenting - clear field names and docstrings

Reference:
    - docs/architecture/registry.md (Registry Pattern Architecture)
    - docs/architecture/cqrs-registry.md (CQRS-specific documentation)
"""

from dataclasses import dataclass
from enum import Enum


class CQRSCategory(str, Enum):
    """Categories for CQRS commands and queries.

    Categories match the domain boundaries and help organize
    commands/queries by their functional area.
    """

    AUTH = "auth"  # Authentication: registration, login, logout, password reset
    SESSION = "session"  # Session management: create, revoke, list
    TOKEN = "token"  # Token operations: generate, rotate
    PROVIDER = "provider"  # Provider connections: connect, disconnect, refresh
    DATA_SYNC = "data_sync"  # Data synchronization: accounts, transactions, holdings
    IMPORT = "import"  # File imports: QFX, OFX, CSV


class CachePolicy(str, Enum):
    """Cache policies for query results.

    Hints for container/infrastructure on how to cache query results.
    """

    NONE = "none"  # No caching (default for most queries)
    SHORT = "short"  # Short TTL (e.g., 1 minute) - frequently changing data
    MEDIUM = "medium"  # Medium TTL (e.g., 5 minutes) - moderately stable data
    LONG = "long"  # Long TTL (e.g., 1 hour) - rarely changing data
    AGGRESSIVE = "aggressive"  # Very long TTL with manual invalidation


@dataclass(frozen=True, kw_only=True)
class CommandMetadata:
    """Metadata for a command in the CQRS registry.

    Commands represent user intent to change system state. Each command
    has a corresponding handler that executes the business logic.

    Attributes:
        command_class: The command dataclass (e.g., RegisterUser).
        handler_class: The handler class (e.g., RegisterUserHandler).
        category: Functional category for organization.
        has_result_dto: Whether handler returns a result DTO (vs simple UUID/bool).
        result_dto_class: The DTO class if has_result_dto is True.
        emits_events: Whether this command publishes domain events.
        requires_transaction: Whether this command needs a database transaction.
        description: Human-readable description for documentation.

    Example:
        >>> CommandMetadata(
        ...     command_class=RegisterUser,
        ...     handler_class=RegisterUserHandler,
        ...     category=CQRSCategory.AUTH,
        ...     emits_events=True,
        ...     requires_transaction=True,
        ...     description="Register new user account with email verification",
        ... )
    """

    command_class: type
    handler_class: type
    category: CQRSCategory
    has_result_dto: bool = False
    result_dto_class: type | None = None
    emits_events: bool = True  # Most commands emit domain events
    requires_transaction: bool = True  # Most commands need DB transaction
    description: str = ""

    def __post_init__(self) -> None:
        """Validate metadata consistency."""
        if self.has_result_dto and self.result_dto_class is None:
            raise ValueError(
                f"Command {self.command_class.__name__} has has_result_dto=True "
                f"but no result_dto_class specified"
            )
        if not self.has_result_dto and self.result_dto_class is not None:
            raise ValueError(
                f"Command {self.command_class.__name__} has result_dto_class "
                f"but has_result_dto=False"
            )


@dataclass(frozen=True, kw_only=True)
class QueryMetadata:
    """Metadata for a query in the CQRS registry.

    Queries represent requests for data. They never change state
    and can be safely cached.

    Attributes:
        query_class: The query dataclass (e.g., GetAccount).
        handler_class: The handler class (e.g., GetAccountHandler).
        category: Functional category for organization.
        is_paginated: Whether this query supports pagination.
        cache_policy: Caching hints for infrastructure.
        description: Human-readable description for documentation.

    Example:
        >>> QueryMetadata(
        ...     query_class=ListAccountsByUser,
        ...     handler_class=ListAccountsHandler,
        ...     category=CQRSCategory.DATA_SYNC,
        ...     is_paginated=True,
        ...     cache_policy=CachePolicy.SHORT,
        ...     description="List all accounts for a user across all connections",
        ... )
    """

    query_class: type
    handler_class: type
    category: CQRSCategory
    is_paginated: bool = False
    cache_policy: CachePolicy = CachePolicy.NONE
    description: str = ""


def get_handler_factory_name(metadata: CommandMetadata | QueryMetadata) -> str:
    """Compute the expected container factory function name for a handler.

    Follows the existing naming convention in container modules:
    - Commands: get_{snake_case_command}_handler
    - Queries: get_{snake_case_query}_handler

    Args:
        metadata: Command or query metadata.

    Returns:
        Expected factory function name.

    Example:
        >>> metadata = CommandMetadata(
        ...     command_class=RegisterUser,
        ...     handler_class=RegisterUserHandler,
        ...     category=CQRSCategory.AUTH,
        ... )
        >>> get_handler_factory_name(metadata)
        'get_register_user_handler'
    """
    if isinstance(metadata, CommandMetadata):
        class_name = metadata.command_class.__name__
    else:
        class_name = metadata.query_class.__name__

    # Convert PascalCase to snake_case
    snake_case = ""
    for i, char in enumerate(class_name):
        if char.isupper() and i > 0:
            snake_case += "_"
        snake_case += char.lower()

    return f"get_{snake_case}_handler"


def get_handler_dependencies(handler_class: type) -> list[str]:
    """Extract dependency names from handler __init__ signature.

    Used by container auto-wiring to determine what dependencies
    to inject when creating handler instances.

    Args:
        handler_class: The handler class to inspect.

    Returns:
        List of dependency parameter names from __init__.

    Example:
        >>> class RegisterUserHandler:
        ...     def __init__(self, user_repo, password_service, event_bus):
        ...         pass
        >>> get_handler_dependencies(RegisterUserHandler)
        ['user_repo', 'password_service', 'event_bus']
    """
    import inspect

    try:
        # Use getattr to avoid mypy's unsound __init__ access warning
        init_method = getattr(handler_class, "__init__", None)
        if init_method is None:
            return []
        sig = inspect.signature(init_method)
        # Skip 'self' parameter
        params = list(sig.parameters.keys())[1:]
        return params
    except (ValueError, TypeError):
        return []
