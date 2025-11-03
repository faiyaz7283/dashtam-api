"""Rename is_trusted_device to is_trusted in sessions table

Revision ID: 462cce711b23
Revises: 1a87a97a6d84
Create Date: 2025-11-03 04:02:07.397528+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "462cce711b23"
down_revision: Union[str, Sequence[str], None] = "1a87a97a6d84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the incorrectly created is_trusted column (if it exists)
    # This was created from SessionBase in the previous migration
    op.drop_column("sessions", "is_trusted")
    # Rename is_trusted_device to is_trusted to match SessionBase interface
    op.alter_column("sessions", "is_trusted_device", new_column_name="is_trusted")


def downgrade() -> None:
    """Downgrade schema."""
    # Rename back to is_trusted_device
    op.alter_column("sessions", "is_trusted", new_column_name="is_trusted_device")
    # Recreate the is_trusted column (that was dropped)
    op.add_column(
        "sessions",
        sa.Column(
            "is_trusted",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
