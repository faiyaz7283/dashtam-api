"""RBAC policy seeder for Casbin authorization.

Seeds default roles, permissions, and role hierarchy into casbin_rule table.
Idempotent via ON CONFLICT DO NOTHING - safe to run on every migration.

After initial seeding, all role/permission changes should be managed
via admin APIs (properly audited, authorized).

Reference:
    - docs/architecture/authorization-architecture.md
    - docs/guides/database-seeding.md
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def seed_rbac_policies(session: AsyncSession) -> None:
    """Seed default RBAC policies. Idempotent via ON CONFLICT DO NOTHING.

    Seeds:
        - Role permissions (readonly, user, admin)
        - Role hierarchy (admin > user > readonly)

    Note:
        After initial seeding, all role/permission changes should be
        managed via admin APIs (properly audited, authorized).

    Args:
        session: Async database session.
    """
    # Define all policies to seed
    # Format: (ptype, v0, v1, v2)
    # For 'p': (ptype, role, resource, action)
    # For 'g': (ptype, child_role, parent_role, "")
    policies: list[tuple[str, str, str, str]] = [
        # =================================================================
        # Role permissions (p = permission)
        # =================================================================
        # readonly role - read-only access to own resources
        ("p", "readonly", "accounts", "read"),
        ("p", "readonly", "transactions", "read"),
        ("p", "readonly", "providers", "read"),
        ("p", "readonly", "sessions", "read"),
        # user role - write access (inherits readonly via role hierarchy)
        ("p", "user", "accounts", "write"),
        ("p", "user", "transactions", "write"),
        ("p", "user", "providers", "write"),
        ("p", "user", "sessions", "write"),
        # admin role - full access (inherits user via role hierarchy)
        ("p", "admin", "users", "read"),
        ("p", "admin", "users", "write"),
        ("p", "admin", "admin", "read"),
        ("p", "admin", "admin", "write"),
        ("p", "admin", "security", "read"),
        ("p", "admin", "security", "write"),
        # =================================================================
        # Role hierarchy (g = grouping/inheritance)
        # admin inherits from user, user inherits from readonly
        # =================================================================
        ("g", "user", "readonly", ""),
        ("g", "admin", "user", ""),
    ]

    seeded_count = 0
    skipped_count = 0

    for ptype, v0, v1, v2 in policies:
        # Check if policy already exists
        result = await session.execute(
            text("""
                SELECT 1 FROM casbin_rule
                WHERE ptype = :ptype AND v0 = :v0 AND v1 = :v1 AND v2 = :v2
                LIMIT 1
            """),
            {"ptype": ptype, "v0": v0, "v1": v1, "v2": v2},
        )

        if result.fetchone() is not None:
            skipped_count += 1
            continue

        # Insert policy (doesn't exist)
        await session.execute(
            text("""
                INSERT INTO casbin_rule (ptype, v0, v1, v2)
                VALUES (:ptype, :v0, :v1, :v2)
            """),
            {"ptype": ptype, "v0": v0, "v1": v1, "v2": v2},
        )
        seeded_count += 1

    logger.info(
        "rbac_seeding_complete",
        seeded=seeded_count,
        skipped=skipped_count,
        total=len(policies),
    )
