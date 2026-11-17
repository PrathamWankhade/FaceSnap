"""record model version on students and add detection review queue

Revision ID: a1b2c3d4e5f6
Revises: 7c1d9e4a2b10
Create Date: 2026-11-17
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7c1d9e4a2b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_student_cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "model_version" not in existing_student_cols:
            batch_op.add_column(sa.Column("model_version", sa.String(length=60), nullable=True))

    inspector = sa.inspect(op.get_bind())
    if "detection_reviews" not in inspector.get_table_names():
        op.create_table(
            "detection_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True, server_default="pending"),
            sa.Column("nearest_uid", sa.String(length=128), nullable=True),
            sa.Column("nearest_distance", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("assigned_to", sa.String(length=128), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(length=128), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=128), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_detection_reviews_detected_at", "detection_reviews", ["detected_at"])
        op.create_index("ix_detection_reviews_status", "detection_reviews", ["status"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "detection_reviews" in inspector.get_table_names():
        op.drop_table("detection_reviews")
    existing_student_cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "model_version" in existing_student_cols:
            batch_op.drop_column("model_version")