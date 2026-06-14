"""Store validated rich map point details.

Revision ID: 20260614_0004
Revises: 20260614_0003
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20260614_0004"
down_revision = "20260614_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "plan_map_points" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("plan_map_points")}
    if "details" not in existing_columns:
        with op.batch_alter_table("plan_map_points") as batch:
            batch.add_column(sa.Column("details", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "plan_map_points" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("plan_map_points")}
    if "details" in existing_columns:
        with op.batch_alter_table("plan_map_points") as batch:
            batch.drop_column("details")
