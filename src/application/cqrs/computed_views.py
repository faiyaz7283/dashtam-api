"""CQRS Registry Computed Views and Helper Functions.

Utility functions for introspecting the CQRS registry.
Used by container auto-wiring, tests, and documentation generation.

Reference:
    - docs/architecture/registry.md
    - docs/architecture/cqrs-registry.md
"""

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.cqrs.metadata import (
        CachePolicy,
        CommandMetadata,
        CQRSCategory,
        QueryMetadata,
    )


def get_all_commands() -> list[type]:
    """Get all registered command classes.

    Returns:
        List of command classes in registry.

    Example:
        >>> commands = get_all_commands()
        >>> len(commands)
        23
        >>> RegisterUser in commands
        True
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY

    return [meta.command_class for meta in COMMAND_REGISTRY]


def get_all_queries() -> list[type]:
    """Get all registered query classes.

    Returns:
        List of query classes in registry.

    Example:
        >>> queries = get_all_queries()
        >>> len(queries)
        18
        >>> GetAccount in queries
        True
    """
    from src.application.cqrs.registry import QUERY_REGISTRY

    return [meta.query_class for meta in QUERY_REGISTRY]


def get_commands_by_category(category: "CQRSCategory") -> list["CommandMetadata"]:
    """Get command metadata filtered by category.

    Args:
        category: CQRSCategory to filter by.

    Returns:
        List of CommandMetadata entries for that category.

    Example:
        >>> from src.application.cqrs.metadata import CQRSCategory
        >>> auth_commands = get_commands_by_category(CQRSCategory.AUTH)
        >>> len(auth_commands)
        7
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY

    return [meta for meta in COMMAND_REGISTRY if meta.category == category]


def get_queries_by_category(category: "CQRSCategory") -> list["QueryMetadata"]:
    """Get query metadata filtered by category.

    Args:
        category: CQRSCategory to filter by.

    Returns:
        List of QueryMetadata entries for that category.

    Example:
        >>> from src.application.cqrs.metadata import CQRSCategory
        >>> data_queries = get_queries_by_category(CQRSCategory.DATA_SYNC)
        >>> len(data_queries)
        14
    """
    from src.application.cqrs.registry import QUERY_REGISTRY

    return [meta for meta in QUERY_REGISTRY if meta.category == category]


def get_command_metadata(command_class: type) -> "CommandMetadata | None":
    """Get metadata for a specific command class.

    Args:
        command_class: The command class to look up.

    Returns:
        CommandMetadata if found, None otherwise.

    Example:
        >>> from src.application.commands.auth_commands import RegisterUser
        >>> meta = get_command_metadata(RegisterUser)
        >>> meta.handler_class.__name__
        'RegisterUserHandler'
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY

    for meta in COMMAND_REGISTRY:
        if meta.command_class == command_class:
            return meta
    return None


def get_query_metadata(query_class: type) -> "QueryMetadata | None":
    """Get metadata for a specific query class.

    Args:
        query_class: The query class to look up.

    Returns:
        QueryMetadata if found, None otherwise.

    Example:
        >>> from src.application.queries.account_queries import GetAccount
        >>> meta = get_query_metadata(GetAccount)
        >>> meta.handler_class.__name__
        'GetAccountHandler'
    """
    from src.application.cqrs.registry import QUERY_REGISTRY

    for meta in QUERY_REGISTRY:
        if meta.query_class == query_class:
            return meta
    return None


def get_commands_with_result_dto() -> list["CommandMetadata"]:
    """Get all commands that return result DTOs.

    Returns:
        List of CommandMetadata where has_result_dto is True.

    Example:
        >>> commands = get_commands_with_result_dto()
        >>> len(commands)  # AuthenticateUser, GenerateAuthTokens, etc.
        8
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY

    return [meta for meta in COMMAND_REGISTRY if meta.has_result_dto]


def get_commands_emitting_events() -> list["CommandMetadata"]:
    """Get all commands that emit domain events.

    Returns:
        List of CommandMetadata where emits_events is True.

    Example:
        >>> commands = get_commands_emitting_events()
        >>> len(commands) > 15
        True
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY

    return [meta for meta in COMMAND_REGISTRY if meta.emits_events]


def get_paginated_queries() -> list["QueryMetadata"]:
    """Get all queries that support pagination.

    Returns:
        List of QueryMetadata where is_paginated is True.

    Example:
        >>> queries = get_paginated_queries()
        >>> any(q.query_class.__name__ == 'ListTransactionsByAccount' for q in queries)
        True
    """
    from src.application.cqrs.registry import QUERY_REGISTRY

    return [meta for meta in QUERY_REGISTRY if meta.is_paginated]


def get_queries_by_cache_policy(cache_policy: "CachePolicy") -> list["QueryMetadata"]:
    """Get queries filtered by cache policy.

    Args:
        cache_policy: CachePolicy to filter by.

    Returns:
        List of QueryMetadata with that cache policy.

    Example:
        >>> from src.application.cqrs.metadata import CachePolicy
        >>> medium_cache = get_queries_by_cache_policy(CachePolicy.MEDIUM)
        >>> len(medium_cache) > 0
        True
    """
    from src.application.cqrs.registry import QUERY_REGISTRY

    return [meta for meta in QUERY_REGISTRY if meta.cache_policy == cache_policy]


def get_statistics() -> dict[str, int | dict[str, int]]:
    """Get registry statistics for documentation and monitoring.

    Returns:
        Dict with counts by category, type, etc.

    Example:
        >>> stats = get_statistics()
        >>> stats['total_commands']
        23
        >>> stats['total_queries']
        18
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY, QUERY_REGISTRY

    return {
        "total_commands": len(COMMAND_REGISTRY),
        "total_queries": len(QUERY_REGISTRY),
        "total_operations": len(COMMAND_REGISTRY) + len(QUERY_REGISTRY),
        "commands_by_category": dict(
            Counter(meta.category.value for meta in COMMAND_REGISTRY)
        ),
        "queries_by_category": dict(
            Counter(meta.category.value for meta in QUERY_REGISTRY)
        ),
        "commands_with_result_dto": sum(
            1 for meta in COMMAND_REGISTRY if meta.has_result_dto
        ),
        "commands_emitting_events": sum(
            1 for meta in COMMAND_REGISTRY if meta.emits_events
        ),
        "commands_requiring_transaction": sum(
            1 for meta in COMMAND_REGISTRY if meta.requires_transaction
        ),
        "paginated_queries": sum(1 for meta in QUERY_REGISTRY if meta.is_paginated),
        "queries_by_cache_policy": dict(
            Counter(meta.cache_policy.value for meta in QUERY_REGISTRY)
        ),
    }


def get_handler_class_for_command(command_class: type) -> type | None:
    """Get the handler class for a command.

    Args:
        command_class: The command class.

    Returns:
        Handler class if found, None otherwise.

    Example:
        >>> from src.application.commands.auth_commands import RegisterUser
        >>> handler = get_handler_class_for_command(RegisterUser)
        >>> handler.__name__
        'RegisterUserHandler'
    """
    meta = get_command_metadata(command_class)
    return meta.handler_class if meta else None


def get_handler_class_for_query(query_class: type) -> type | None:
    """Get the handler class for a query.

    Args:
        query_class: The query class.

    Returns:
        Handler class if found, None otherwise.

    Example:
        >>> from src.application.queries.account_queries import GetAccount
        >>> handler = get_handler_class_for_query(GetAccount)
        >>> handler.__name__
        'GetAccountHandler'
    """
    meta = get_query_metadata(query_class)
    return meta.handler_class if meta else None


def get_all_handler_classes() -> list[type]:
    """Get all registered handler classes (commands + queries).

    Returns:
        List of all handler classes.

    Example:
        >>> handlers = get_all_handler_classes()
        >>> len(handlers)  # Unique handlers
        41
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY, QUERY_REGISTRY

    # Use set to deduplicate (some commands share handlers)
    handlers: set[type] = set()
    for cmd_meta in COMMAND_REGISTRY:
        handlers.add(cmd_meta.handler_class)
    for qry_meta in QUERY_REGISTRY:
        handlers.add(qry_meta.handler_class)
    return list(handlers)


def validate_registry_consistency() -> list[str]:
    """Validate registry for common issues.

    Returns:
        List of error messages. Empty if registry is consistent.

    Example:
        >>> errors = validate_registry_consistency()
        >>> len(errors)
        0
    """
    from src.application.cqrs.registry import COMMAND_REGISTRY, QUERY_REGISTRY

    errors: list[str] = []

    # Check for duplicate command classes
    command_classes = [meta.command_class for meta in COMMAND_REGISTRY]
    if len(command_classes) != len(set(command_classes)):
        errors.append("Duplicate command classes in COMMAND_REGISTRY")

    # Check for duplicate query classes
    query_classes = [meta.query_class for meta in QUERY_REGISTRY]
    if len(query_classes) != len(set(query_classes)):
        errors.append("Duplicate query classes in QUERY_REGISTRY")

    # Check that handlers have handle() method
    for cmd_meta in COMMAND_REGISTRY:
        if not hasattr(cmd_meta.handler_class, "handle"):
            errors.append(
                f"Command handler {cmd_meta.handler_class.__name__} missing handle() method"
            )

    for qry_meta in QUERY_REGISTRY:
        if not hasattr(qry_meta.handler_class, "handle"):
            errors.append(
                f"Query handler {qry_meta.handler_class.__name__} missing handle() method"
            )

    return errors
