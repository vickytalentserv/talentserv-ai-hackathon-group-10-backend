"""004 favorites and inquiries

Revision ID: 004_favorites_inquiries
Revises: 003_requirements
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_favorites_inquiries"
down_revision: Union[str, None] = "003_requirements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("listing_key", sa.String(length=80), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "listing_key", name="uq_favorites_user_listing"),
    )
    op.create_index(op.f("ix_favorites_listing_key"), "favorites", ["listing_key"], unique=False)
    op.create_index(op.f("ix_favorites_property_id"), "favorites", ["property_id"], unique=False)
    op.create_index(op.f("ix_favorites_user_id"), "favorites", ["user_id"], unique=False)

    op.create_table(
        "inquiries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("listing_key", sa.String(length=80), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inquiries_listing_key"), "inquiries", ["listing_key"], unique=False)
    op.create_index(op.f("ix_inquiries_property_id"), "inquiries", ["property_id"], unique=False)
    op.create_index(op.f("ix_inquiries_user_id"), "inquiries", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inquiries_user_id"), table_name="inquiries")
    op.drop_index(op.f("ix_inquiries_property_id"), table_name="inquiries")
    op.drop_index(op.f("ix_inquiries_listing_key"), table_name="inquiries")
    op.drop_table("inquiries")
    op.drop_index(op.f("ix_favorites_user_id"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_property_id"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_listing_key"), table_name="favorites")
    op.drop_table("favorites")
