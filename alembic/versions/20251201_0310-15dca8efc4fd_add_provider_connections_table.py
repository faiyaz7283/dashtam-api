"""add_provider_connections_table

Revision ID: 15dca8efc4fd
Revises: 421e9f50970f
Create Date: 2025-12-01 03:10:34.407563+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "15dca8efc4fd"
down_revision: Union[str, Sequence[str], None] = "421e9f50970f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create provider_connections table."""
    op.create_table(
        "provider_connections",
        # Primary key and timestamps from BaseMutableModel
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # User relationship
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=False,
            comment="User who owns this connection",
        ),
        # Provider identification
        sa.Column(
            "provider_id",
            sa.Uuid(),
            nullable=False,
            comment="Provider UUID (FK to providers table in future)",
        ),
        sa.Column(
            "provider_slug",
            sa.String(length=50),
            nullable=False,
            comment="Denormalized provider identifier (e.g., 'schwab')",
        ),
        # Connection state
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Connection status: pending, active, expired, revoked, failed, disconnected",
        ),
        sa.Column(
            "alias",
            sa.String(length=100),
            nullable=True,
            comment="User-defined nickname (e.g., 'My Schwab IRA')",
        ),
        # Credentials
        sa.Column(
            "credential_type",
            sa.String(length=20),
            nullable=True,
            comment="Credential type: oauth2, api_key, link_token, certificate, custom",
        ),
        sa.Column(
            "encrypted_credentials",
            sa.LargeBinary(),
            nullable=True,
            comment="AES-256 encrypted credential blob",
        ),
        sa.Column(
            "credentials_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When credentials expire (for proactive refresh)",
        ),
        # Timestamps
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When connection was first established",
        ),
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful data synchronization",
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Individual indexes
    op.create_index(
        op.f("ix_provider_connections_user_id"),
        "provider_connections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_connections_provider_slug"),
        "provider_connections",
        ["provider_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_connections_status"),
        "provider_connections",
        ["status"],
        unique=False,
    )

    # Composite indexes
    op.create_index(
        "idx_provider_connections_user_provider",
        "provider_connections",
        ["user_id", "provider_id"],
        unique=False,
    )
    op.create_index(
        "idx_provider_connections_active",
        "provider_connections",
        ["user_id", "status"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_provider_connections_expiring",
        "provider_connections",
        ["credentials_expires_at"],
        unique=False,
        postgresql_where=sa.text(
            "status = 'active' AND credentials_expires_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    """Drop provider_connections table."""
    # Drop indexes first
    op.drop_index(
        "idx_provider_connections_expiring",
        table_name="provider_connections",
        postgresql_where=sa.text(
            "status = 'active' AND credentials_expires_at IS NOT NULL"
        ),
    )
    op.drop_index(
        "idx_provider_connections_active",
        table_name="provider_connections",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "idx_provider_connections_user_provider",
        table_name="provider_connections",
    )
    op.drop_index(
        op.f("ix_provider_connections_status"),
        table_name="provider_connections",
    )
    op.drop_index(
        op.f("ix_provider_connections_provider_slug"),
        table_name="provider_connections",
    )
    op.drop_index(
        op.f("ix_provider_connections_user_id"),
        table_name="provider_connections",
    )

    # Drop table
    op.drop_table("provider_connections")
