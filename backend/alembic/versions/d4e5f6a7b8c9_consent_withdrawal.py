"""consent withdrawal timestamp on students

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-24

Withdrawal is distinct from deletion: the student keeps their profile and
history but asks FaceSnap to stop processing their biometrics. Existing rows
stay NULL — nobody is withdrawn by default, and the column is nullable on
purpose so a backfill cannot invent a withdrawal.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent on purpose: a create_all-era database may already have the
    # column even though no Alembic revision recorded it.
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "consent_withdrawn_at" not in existing:
            batch_op.add_column(
                sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True)
            )


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "consent_withdrawn_at" in existing:
            batch_op.drop_column("consent_withdrawn_at")