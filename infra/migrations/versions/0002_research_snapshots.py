"""Deduplicated immutable inputs for reproducible research runs."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_snapshots",
        sa.Column("data_hash", sa.String(64), primary_key=True),
        sa.Column("compressed_json", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("data_snapshots")
