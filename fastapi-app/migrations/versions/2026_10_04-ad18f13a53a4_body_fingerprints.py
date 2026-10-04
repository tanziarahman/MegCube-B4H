"""body fingerprints

Revision ID: ad18f13a53a4
Revises: 4c11bccf503b
Create Date: 2026-10-04 13:30:00.000000

Whole-body (clothing) fingerprints on sightings, so different people can be told apart within a day
when faces from the ceiling cameras are too unclear to compare.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate may reference sqlmodel types)
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ad18f13a53a4'
down_revision: Union[str, Sequence[str], None] = '4c11bccf503b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sightings', sa.Column('body_embedding', postgresql.ARRAY(sa.REAL()), nullable=True))
    op.add_column('sightings', sa.Column('body_embedding_model', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sightings', 'body_embedding_model')
    op.drop_column('sightings', 'body_embedding')
