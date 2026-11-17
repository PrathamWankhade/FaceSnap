"""add hash chain columns to audit_log

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-17
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("audit_log")}
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        if "prev_hash" not in existing:
            batch_op.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))
        if "row_hash" not in existing:
            batch_op.add_column(sa.Column("row_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("audit_log")}
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        if "row_hash" in existing:
            batch_op.drop_column("row_hash")
        if "prev_hash" in existing:
            batch_op.drop_column("prev_hash")