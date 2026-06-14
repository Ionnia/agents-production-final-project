"""Initial backend schema."""

from alembic import op

from travel_backend import models  # noqa: F401
from travel_backend.database import Base

revision = "20260614_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
