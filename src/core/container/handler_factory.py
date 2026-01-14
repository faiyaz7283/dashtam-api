"""Handler Factory Generator - Auto-wire handler dependencies from registry.

This module provides automatic dependency injection for CQRS handlers
based on their __init__ type hints. It introspects handler constructors
and resolves dependencies from the container.

Architecture:
- Uses Python's inspect module to analyze handler signatures
- Maps protocol types to container factory functions
- Creates request-scoped handler instances with injected dependencies

Usage:
    from src.core.container.handler_factory import create_handler

    # In router
    async def get_handler(session: AsyncSession = Depends(get_db_session)):
        return await create_handler(RegisterUserHandler, session)

Reference:
    - docs/architecture/cqrs-registry.md
    - docs/architecture/dependency-injection.md
"""

import inspect
from typing import Any, TypeVar, get_type_hints

from sqlalchemy.ext.asyncio import AsyncSession

# Type variable for handler classes
T = TypeVar("T")


# =============================================================================
# Dependency Type Mappings
# =============================================================================

# Repository types that need session injection
REPOSITORY_TYPES: dict[str, str] = {
    "UserRepository": "src.infrastructure.persistence.repositories.UserRepository",
    "AccountRepository": "src.infrastructure.persistence.repositories.AccountRepository",
    "TransactionRepository": "src.infrastructure.persistence.repositories.TransactionRepository",
    "HoldingRepository": "src.infrastructure.persistence.repositories.HoldingRepository",
    "ProviderConnectionRepository": "src.infrastructure.persistence.repositories.ProviderConnectionRepository",
    "SessionRepository": "src.infrastructure.persistence.repositories.SessionRepository",
    "RefreshTokenRepository": "src.infrastructure.persistence.repositories.RefreshTokenRepository",
    "SecurityConfigRepository": "src.infrastructure.persistence.repositories.SecurityConfigRepository",
    "BalanceSnapshotRepository": "src.infrastructure.persistence.repositories.BalanceSnapshotRepository",
    "EmailVerificationTokenRepository": "src.infrastructure.persistence.repositories.EmailVerificationTokenRepository",
    "PasswordResetTokenRepository": "src.infrastructure.persistence.repositories.PasswordResetTokenRepository",
    "ProviderRepository": "src.infrastructure.persistence.repositories.ProviderRepository",
}

# Service/protocol types that are app-scoped singletons
SINGLETON_TYPES: dict[str, str] = {
    "EventBusProtocol": "get_event_bus",
    "PasswordHashingProtocol": "get_password_service",
    "TokenGenerationProtocol": "get_token_service",
    "CacheProtocol": "get_cache",
    "CacheKeysProtocol": "get_cache_keys",
    "CacheMetricsProtocol": "get_cache_metrics",
    "LoggerProtocol": "get_logger",
    "EmailServiceProtocol": "get_email_service",
}


def get_type_name(annotation: Any) -> str:
    """Extract type name from annotation.

    Handles both class types and string forward references.

    Args:
        annotation: Type annotation (class or string).

    Returns:
        Type name as string.
    """
    if annotation is None:
        return "None"

    # Handle Optional types (Union with None)
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # For Union types, get the first non-None type
        args = getattr(annotation, "__args__", ())
        for arg in args:
            if arg is not type(None):
                return get_type_name(arg)
        return "None"

    # Handle class types
    if isinstance(annotation, type):
        return annotation.__name__

    # Handle string annotations
    if isinstance(annotation, str):
        return annotation.split(".")[-1]

    # Fallback
    return str(annotation).split(".")[-1].rstrip("'>")


def analyze_handler_dependencies(handler_class: type) -> dict[str, dict[str, Any]]:
    """Analyze handler __init__ to discover dependencies.

    Args:
        handler_class: Handler class to analyze.

    Returns:
        Dict mapping param name -> {type_name, annotation, is_optional}.

    Example:
        >>> deps = analyze_handler_dependencies(RegisterUserHandler)
        >>> deps['user_repo']['type_name']
        'UserRepository'
    """
    try:
        # Use getattr to avoid mypy's unsound __init__ access warning
        init_method = getattr(handler_class, "__init__", None)
        if init_method is None:
            return {}
        # Get type hints (resolves forward references)
        hints = get_type_hints(init_method)
    except Exception:
        # Fallback to signature annotations if get_type_hints fails
        init_method = getattr(handler_class, "__init__", None)
        if init_method is None:
            return {}
        sig = inspect.signature(init_method)
        hints = {
            name: param.annotation
            for name, param in sig.parameters.items()
            if name != "self" and param.annotation != inspect.Parameter.empty
        }

    # Remove 'return' from hints
    hints.pop("return", None)

    dependencies: dict[str, dict[str, Any]] = {}

    for param_name, annotation in hints.items():
        if param_name == "self":
            continue

        type_name = get_type_name(annotation)

        # Check if optional (Union with None)
        is_optional = False
        origin = getattr(annotation, "__origin__", None)
        if origin is not None:
            args = getattr(annotation, "__args__", ())
            is_optional = type(None) in args

        dependencies[param_name] = {
            "type_name": type_name,
            "annotation": annotation,
            "is_optional": is_optional,
        }

    return dependencies


def _get_repository_instance(
    type_name: str,
    session: AsyncSession,
) -> Any:
    """Create repository instance with session.

    Args:
        type_name: Repository type name.
        session: Database session for repository.

    Returns:
        Repository instance.

    Raises:
        ValueError: If repository type not found.
    """
    # Import repositories dynamically to avoid circular imports
    from src.infrastructure.persistence.repositories import (
        AccountRepository,
        BalanceSnapshotRepository,
        EmailVerificationTokenRepository,
        HoldingRepository,
        PasswordResetTokenRepository,
        ProviderConnectionRepository,
        ProviderRepository,
        RefreshTokenRepository,
        SessionRepository,
        TransactionRepository,
        UserRepository,
    )

    # Map type names to classes
    repo_classes: dict[str, type] = {
        "UserRepository": UserRepository,
        "AccountRepository": AccountRepository,
        "TransactionRepository": TransactionRepository,
        "HoldingRepository": HoldingRepository,
        "ProviderConnectionRepository": ProviderConnectionRepository,
        "SessionRepository": SessionRepository,
        "RefreshTokenRepository": RefreshTokenRepository,
        "BalanceSnapshotRepository": BalanceSnapshotRepository,
        "EmailVerificationTokenRepository": EmailVerificationTokenRepository,
        "PasswordResetTokenRepository": PasswordResetTokenRepository,
        "ProviderRepository": ProviderRepository,
    }

    if type_name not in repo_classes:
        raise ValueError(f"Unknown repository type: {type_name}")

    return repo_classes[type_name](session=session)


def _get_singleton_instance(type_name: str) -> Any:
    """Get singleton service instance from container.

    Args:
        type_name: Service/protocol type name.

    Returns:
        Singleton instance.

    Raises:
        ValueError: If singleton type not found.
    """
    from src.core.container.events import get_event_bus
    from src.core.container.infrastructure import (
        get_cache,
        get_cache_keys,
        get_cache_metrics,
        get_email_service,
        get_logger,
        get_password_service,
        get_token_service,
    )

    singleton_factories: dict[str, Any] = {
        "EventBusProtocol": get_event_bus,
        "PasswordHashingProtocol": get_password_service,
        "TokenGenerationProtocol": get_token_service,
        "CacheProtocol": get_cache,
        "CacheKeysProtocol": get_cache_keys,
        "CacheMetricsProtocol": get_cache_metrics,
        "LoggerProtocol": get_logger,
        "EmailServiceProtocol": get_email_service,
    }

    if type_name not in singleton_factories:
        raise ValueError(f"Unknown singleton type: {type_name}")

    return singleton_factories[type_name]()


def _is_repository_type(type_name: str) -> bool:
    """Check if type is a repository that needs session."""
    return type_name in REPOSITORY_TYPES or type_name.endswith("Repository")


def _is_singleton_type(type_name: str) -> bool:
    """Check if type is a singleton service."""
    return type_name in SINGLETON_TYPES or type_name.endswith("Protocol")


async def create_handler(
    handler_class: type[T],
    session: AsyncSession,
    **overrides: Any,
) -> T:
    """Create handler instance with auto-wired dependencies.

    Introspects handler __init__ and resolves dependencies:
    - Repositories: Created with session
    - Singletons: Retrieved from container
    - Overrides: Provided explicitly

    Args:
        handler_class: Handler class to instantiate.
        session: Database session for repositories.
        **overrides: Explicit dependency overrides.

    Returns:
        Handler instance with injected dependencies.

    Raises:
        ValueError: If dependency cannot be resolved.

    Example:
        >>> handler = await create_handler(RegisterUserHandler, session)
        >>> result = await handler.handle(command)
    """
    dependencies = analyze_handler_dependencies(handler_class)
    resolved: dict[str, Any] = {}

    for param_name, dep_info in dependencies.items():
        type_name = dep_info["type_name"]
        is_optional = dep_info["is_optional"]

        # Check for explicit override
        if param_name in overrides:
            resolved[param_name] = overrides[param_name]
            continue

        # Try to resolve dependency
        try:
            if _is_repository_type(type_name):
                resolved[param_name] = _get_repository_instance(type_name, session)
            elif _is_singleton_type(type_name):
                resolved[param_name] = _get_singleton_instance(type_name)
            elif is_optional:
                resolved[param_name] = None
            else:
                raise ValueError(
                    f"Cannot resolve dependency '{param_name}' "
                    f"of type '{type_name}' for {handler_class.__name__}"
                )
        except ValueError:
            if is_optional:
                resolved[param_name] = None
            else:
                raise

    return handler_class(**resolved)


def get_supported_dependencies() -> dict[str, list[str]]:
    """Get list of supported dependency types.

    Returns:
        Dict with 'repositories' and 'singletons' lists.
    """
    return {
        "repositories": list(REPOSITORY_TYPES.keys()),
        "singletons": list(SINGLETON_TYPES.keys()),
    }
