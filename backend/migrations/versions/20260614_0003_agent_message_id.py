"""Store agent message ids separately from backend message ids.

Revision ID: 20260614_0003
Revises: 20260614_0002
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20260614_0003"
down_revision = "20260614_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("messages")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    if "agent_message_id" not in existing_columns:
        with op.batch_alter_table("messages") as batch:
            batch.add_column(sa.Column("agent_message_id", sa.String(length=200), nullable=True))
    if "ix_messages_agent_message_id" not in existing_indexes:
        with op.batch_alter_table("messages") as batch:
            batch.create_index("ix_messages_agent_message_id", ["agent_message_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("messages")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    if "agent_message_id" not in existing_columns:
        return
    with op.batch_alter_table("messages") as batch:
        if "ix_messages_agent_message_id" in existing_indexes:
            batch.drop_index("ix_messages_agent_message_id")
        batch.drop_column("agent_message_id")
