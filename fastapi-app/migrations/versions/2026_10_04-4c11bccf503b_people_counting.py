"""people counting

Revision ID: 4c11bccf503b
Revises: 3172e989e4e3
Create Date: 2026-10-04 11:45:00.000000

sightings gets box_id and recognition_result;
cameras default to the merged counting basis now that face and body tracks are paired.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate may reference sqlmodel types)


# revision identifiers, used by Alembic.
revision: str = '4c11bccf503b'
down_revision: Union[str, Sequence[str], None] = '3172e989e4e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOT NULL without a default: fine because nothing wrote to sightings before this revision
    # (if something did, this fails instead of guessing a box).
    op.add_column('sightings', sa.Column('box_id', sa.Integer(), nullable=False))
    op.add_column('sightings', sa.Column('recognition_result', sa.String(length=10), nullable=True))
    op.create_foreign_key(op.f('fk_sightings_box_id_boxes'), 'sightings', 'boxes', ['box_id'], ['id'],
                          ondelete='CASCADE')
    op.create_check_constraint(op.f('ck_sightings_recognition_result'), 'sightings',
                               "recognition_result IN ('matched', 'stranger')")
    # Data: the merged basis is the right unit now that face + body pairing is known.
    op.execute("UPDATE cameras SET count_basis = 'merged' WHERE count_basis = 'face'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE cameras SET count_basis = 'face' WHERE count_basis = 'merged'")
    op.drop_constraint(op.f('ck_sightings_recognition_result'), 'sightings', type_='check')
    op.drop_constraint(op.f('fk_sightings_box_id_boxes'), 'sightings', type_='foreignkey')
    op.drop_column('sightings', 'recognition_result')
    op.drop_column('sightings', 'box_id')
