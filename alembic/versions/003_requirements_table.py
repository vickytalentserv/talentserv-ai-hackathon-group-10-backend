"""003 requirements table

Revision ID: 003_requirements
Revises: 002_property_fields
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_requirements"
down_revision: Union[str, None] = "002_property_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=20), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("budget_min", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("budget_max", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("budget_currency", sa.String(length=3), nullable=False),
        sa.Column("locality", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("property_type", sa.String(length=50), nullable=True),
        sa.Column("parser", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_requirements_user_id"), "requirements", ["user_id"], unique=False)
    op.create_index(op.f("ix_requirements_city"), "requirements", ["city"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_requirements_city"), table_name="requirements")
    op.drop_index(op.f("ix_requirements_user_id"), table_name="requirements")
    op.drop_table("requirements")
