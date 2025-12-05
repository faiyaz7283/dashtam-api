"""Authorization dependency factories.

Casbin RBAC enforcement for role and permission checks.
Enforcer is initialized at application startup.

Reference:
    See docs/architecture/authorization-architecture.md for complete
    RBAC patterns and permission specifications.
"""

from typing import TYPE_CHECKING

from fastapi import Depends

from src.core.config import settings
from src.core.container.infrastructure import get_audit

if TYPE_CHECKING:
    from casbin import AsyncEnforcer

    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.authorization_protocol import AuthorizationProtocol


# Module-level state for enforcer singleton
_enforcer: "AsyncEnforcer | None" = None


# ============================================================================
# Authorization (Casbin RBAC)
# ============================================================================


async def init_enforcer() -> "AsyncEnforcer":
    """Initialize Casbin AsyncEnforcer at application startup.

    Creates enforcer with:
    - Model config from infrastructure/authorization/model.conf
    - PostgreSQL adapter for persistent policy storage

    MUST be called during FastAPI lifespan startup.
    Enforcer is app-scoped singleton (stored in _enforcer module variable).

    Returns:
        Initialized AsyncEnforcer instance.

    Raises:
        RuntimeError: If enforcer is already initialized.

    Reference:
        - docs/architecture/authorization-architecture.md
    """
    global _enforcer

    if _enforcer is not None:
        raise RuntimeError("Enforcer already initialized")

    import os

    import casbin
    from casbin_async_sqlalchemy_adapter import Adapter as CasbinSQLAdapter

    from src.core.container.infrastructure import get_logger

    # Model config path (relative to src/core/container/)
    model_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "infrastructure",
        "authorization",
        "model.conf",
    )

    # Create PostgreSQL adapter for policy storage
    adapter = CasbinSQLAdapter(settings.database_url)

    # Create async enforcer
    _enforcer = casbin.AsyncEnforcer(model_path, adapter)

    # Load policies from database
    await _enforcer.load_policy()

    get_logger().info(
        "casbin_enforcer_initialized",
        model_path=model_path,
    )

    return _enforcer


def get_enforcer() -> "AsyncEnforcer":
    """Get Casbin AsyncEnforcer singleton.

    MUST be called after init_enforcer() during startup.

    Returns:
        The initialized enforcer.

    Raises:
        RuntimeError: If called before init_enforcer().
    """
    if _enforcer is None:
        raise RuntimeError(
            "Enforcer not initialized. Call init_enforcer() during startup."
        )
    return _enforcer


async def get_authorization(
    audit: "AuditProtocol" = Depends(get_audit),
) -> "AuthorizationProtocol":
    """Get authorization adapter (request-scoped).

    Creates CasbinAdapter with:
    - App-scoped enforcer (pre-initialized at startup)
    - Request-scoped audit (for per-request audit logging)
    - App-scoped cache, event_bus, logger

    Args:
        audit: Request-scoped audit adapter for logging authorization checks.

    Returns:
        CasbinAdapter implementing AuthorizationProtocol.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from src.domain.protocols import AuthorizationProtocol

        @router.get("/accounts")
        async def list_accounts(
            auth: AuthorizationProtocol = Depends(get_authorization),
            user: User = Depends(get_current_user),
        ):
            if not await auth.check_permission(user.id, "accounts", "read"):
                raise HTTPException(403, "Permission denied")
            ...

    Reference:
        - docs/architecture/authorization-architecture.md
    """
    from src.infrastructure.authorization.casbin_adapter import CasbinAdapter

    from src.core.container.events import get_event_bus
    from src.core.container.infrastructure import get_cache, get_logger

    return CasbinAdapter(
        enforcer=get_enforcer(),
        cache=get_cache(),
        audit=audit,
        event_bus=get_event_bus(),
        logger=get_logger(),
    )
