"""Store the complete backend-to-agent run mapping.

Revision ID: 20260614_0002
Revises: 20260614_0001
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20260614_0002"
down_revision = "20260614_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    if {"group_id", "agent_thread_id", "agent_stream_url"} <= existing_columns:
        return
    with op.batch_alter_table("runs") as batch:
        if "group_id" not in existing_columns:
            batch.add_column(sa.Column("group_id", sa.String(), nullable=True))
        if "agent_thread_id" not in existing_columns:
            batch.add_column(sa.Column("agent_thread_id", sa.String(), nullable=True))
        if "agent_stream_url" not in existing_columns:
            batch.add_column(sa.Column("agent_stream_url", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_runs_group_id_travel_groups",
            "travel_groups",
            ["group_id"],
            ["id"],
        )
        batch.create_index("ix_runs_group_id", ["group_id"])
        batch.create_index("ix_runs_agent_thread_id", ["agent_thread_id"])


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.drop_index("ix_runs_agent_thread_id")
        batch.drop_index("ix_runs_group_id")
        batch.drop_constraint("fk_runs_group_id_travel_groups", type_="foreignkey")
        batch.drop_column("agent_stream_url")
        batch.drop_column("agent_thread_id")
        batch.drop_column("group_id")
