"""record student consent version at enrollment

Revision ID: 7c1d9e4a2b10
Revises: 5a3501be40cf
Create Date: 2026-11-17

Consent is evidence, not a checkbox in the UI: the database records which
notice version the student accepted and when. Existing rows stay NULL (they
predate versioning) so an institution can query who needs re-consent. The
columns are nullable on purpose — a backfill cannot invent consent.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c1d9e4a2b10"
down_revision: Union[str, None] = "5a3501be40cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent on purpose: a create_all-era database may already have these
    # columns even though no Alembic revision recorded them. Stamping the
    # baseline and upgrading must not fail on a column that is already there.
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "consent_version" not in existing:
            batch_op.add_column(sa.Column("consent_version", sa.String(length=30), nullable=True))
        if "consent_at" not in existing:
            batch_op.add_column(sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("students")}
    with op.batch_alter_table("students", schema=None) as batch_op:
        if "consent_at" in existing:
            batch_op.drop_column("consent_at")
        if "consent_version" in existing:
            batch_op.drop_column("consent_version")
