"""dashboard stats

Revision ID: 9f4c2e7a1b6d
Revises: ad18f13a53a4
Create Date: 2026-10-05 00:00:00.000000

Adds additive per-kind dashboard bucket counts, distinct per-day dashboard stats, and an index
for reading one box's event history efficiently.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c2e7a1b6d"
down_revision: Union[str, Sequence[str], None] = "ad18f13a53a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("count_buckets", sa.Column("matched_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("stranger_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("face_capture_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("body_capture_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("low_confidence_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("low_liveness_events", sa.Integer(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("identity_score_sum", sa.Float(), server_default="0", nullable=False))
    op.add_column("count_buckets", sa.Column("identity_score_count", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "daily_stats",
        sa.Column("box_id", sa.Integer(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("tracked_encounters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("face_encounters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("body_encounters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recognized_encounters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stranger_encounters", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recognized_capture_tracks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unique_recognized_people", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["box_id"], ["boxes.id"], name="fk_daily_stats_box_id_boxes", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("box_id", "local_date", name="pk_daily_stats"),
    )
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_events_box_time", "events", ["box_id", "occurred_at"], unique=False,
            postgresql_concurrently=True, if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_events_box_time", table_name="events", postgresql_concurrently=True)
    op.drop_table("daily_stats")
    op.drop_column("count_buckets", "identity_score_count")
    op.drop_column("count_buckets", "identity_score_sum")
    op.drop_column("count_buckets", "low_liveness_events")
    op.drop_column("count_buckets", "low_confidence_events")
    op.drop_column("count_buckets", "body_capture_events")
    op.drop_column("count_buckets", "face_capture_events")
    op.drop_column("count_buckets", "stranger_events")
    op.drop_column("count_buckets", "matched_events")
