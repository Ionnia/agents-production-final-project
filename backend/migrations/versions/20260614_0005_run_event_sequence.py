"""Allocate run event sequences atomically.

Revision ID: 20260614_0005
Revises: 20260614_0004
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20260614_0005"
down_revision = "20260614_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "runs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    if "event_sequence" not in existing_columns:
        with op.batch_alter_table("runs") as batch:
            batch.add_column(
                sa.Column("event_sequence", sa.Integer(), nullable=False, server_default="0")
            )
    bind.execute(
        sa.text(
            """
            UPDATE runs
            SET event_sequence = COALESCE(
                (
                    SELECT MAX(run_events.sequence)
                    FROM run_events
                    WHERE run_events.run_id = runs.id
                ),
                0
            )
            """
        )
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "runs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    if "event_sequence" in existing_columns:
        with op.batch_alter_table("runs") as batch:
            batch.drop_column("event_sequence")
