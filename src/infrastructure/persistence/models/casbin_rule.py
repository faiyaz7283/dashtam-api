"""Casbin rule database model for RBAC policy storage.

This module defines the CasbinRule model that stores Casbin RBAC policies.
The table structure matches what casbin-async-sqlalchemy-adapter expects.

Policy Types (ptype):
    - 'p': Permission rules (role, resource, action)
    - 'g': Role grouping rules (user/role, parent_role)

Reference:
    - docs/architecture/authorization-architecture.md
    - docs/guides/database-seeding.md
"""

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseModel


class CasbinRule(BaseModel):
    """Casbin rule model for RBAC policy storage.

    This table stores all Casbin RBAC policies including:
    - Permission rules: Which roles can access which resources
    - Role groupings: Role inheritance hierarchy

    Note:
        Uses Integer ID (not UUID) to match Casbin adapter expectations.
        The id column overrides the UUID from BaseModel.

    Policy Examples:
        Permission rule (ptype='p'):
            ptype='p', v0='admin', v1='users', v2='write'
            Means: admin role can write to users resource

        Role grouping (ptype='g'):
            ptype='g', v0='admin', v1='user'
            Means: admin inherits from user role

    Fields:
        id: Auto-incrementing integer primary key
        ptype: Policy type ('p' for permission, 'g' for grouping)
        v0-v2: Policy values (meaning depends on ptype)

    Seeding:
        Initial policies are seeded via rbac_seeder.py after migrations.
        Subsequent changes are managed through admin APIs.
    """

    __tablename__ = "casbin_rule"

    # Override id to use Integer (Casbin adapter expects this)
    id: Mapped[int] = mapped_column(  # type: ignore[assignment]
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    # Policy type: 'p' for permission, 'g' for role grouping
    ptype: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy type: 'p' (permission) or 'g' (role grouping)",
    )

    # Policy values v0-v5 (usage depends on policy type)
    # For 'p': v0=role, v1=resource, v2=action
    # For 'g': v0=child_role, v1=parent_role
    v0: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 0 (role for 'p', child for 'g')",
    )

    v1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 1 (resource for 'p', parent for 'g')",
    )

    v2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 2 (action for 'p', unused for 'g')",
    )

    # v3-v5 columns required by casbin-async-sqlalchemy-adapter.
    # Reserved for future: multi-tenancy (domains) or ABAC.
    v3: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 3 (reserved for domains/ABAC)",
    )

    v4: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 4 (reserved for domains/ABAC)",
    )

    v5: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Policy value 5 (reserved for domains/ABAC)",
    )

    # Indexes for efficient policy lookups
    __table_args__ = (
        Index("idx_casbin_rule_ptype", "ptype"),
        Index("idx_casbin_rule_v0", "v0"),
        Index("idx_casbin_rule_v0_v1_v2", "v0", "v1", "v2"),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of the rule.
        """
        return (
            f"<CasbinRule(ptype={self.ptype}, "
            f"v0={self.v0}, v1={self.v1}, v2={self.v2}, "
            f"v3={self.v3}, v4={self.v4}, v5={self.v5})>"
        )
