"""add priority and category to detection_reviews

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-17
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("detection_reviews")}
    with op.batch_alter_table("detection_reviews", schema=None) as batch_op:
        if "priority" not in existing:
            batch_op.add_column(sa.Column("priority", sa.String(length=10), nullable=True, server_default="medium"))
        if "category" not in existing:
            batch_op.add_column(sa.Column("category", sa.String(length=30), nullable=True, server_default="unknown_face"))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("detection_reviews")}
    with op.batch_alter_table("detection_reviews", schema=None) as batch_op:
        if "category" in existing:
            batch_op.drop_column("category")
        if "priority" in existing:
            batch_op.drop_column("priority")