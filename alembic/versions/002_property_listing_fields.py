"""property listing fields for ingestion

Revision ID: 002_property_fields
Revises: 001_initial
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_property_fields"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("external_id", sa.String(length=64), nullable=True))
    op.add_column("properties", sa.Column("source", sa.String(length=50), nullable=True))
    op.add_column("properties", sa.Column("source_url", sa.String(length=512), nullable=True))
    op.add_column("properties", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("properties", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("properties", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("properties", sa.Column("state", sa.String(length=2), nullable=True))
    op.add_column("properties", sa.Column("zip_code", sa.String(length=10), nullable=True))
    op.add_column("properties", sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column("properties", sa.Column("bedrooms", sa.Integer(), nullable=True))
    op.add_column("properties", sa.Column("bathrooms", sa.Numeric(precision=3, scale=1), nullable=True))
    op.add_column("properties", sa.Column("square_feet", sa.Integer(), nullable=True))
    op.add_column("properties", sa.Column("property_type", sa.String(length=50), nullable=True))
    op.add_column("properties", sa.Column("listing_status", sa.String(length=20), nullable=True))
    op.add_column("properties", sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column("properties", sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True))

    op.alter_column("properties", "owner_id", existing_type=sa.Integer(), nullable=True)

    op.create_index(op.f("ix_properties_source"), "properties", ["source"], unique=False)
    op.create_index(op.f("ix_properties_city"), "properties", ["city"], unique=False)
    op.create_index(op.f("ix_properties_state"), "properties", ["state"], unique=False)
    op.create_index(op.f("ix_properties_listing_status"), "properties", ["listing_status"], unique=False)
    op.create_index(
        "uq_properties_source_external_id",
        "properties",
        ["source", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_properties_source_external_id", table_name="properties")
    op.drop_index(op.f("ix_properties_listing_status"), table_name="properties")
    op.drop_index(op.f("ix_properties_state"), table_name="properties")
    op.drop_index(op.f("ix_properties_city"), table_name="properties")
    op.drop_index(op.f("ix_properties_source"), table_name="properties")

    op.alter_column("properties", "owner_id", existing_type=sa.Integer(), nullable=False)

    op.drop_column("properties", "longitude")
    op.drop_column("properties", "latitude")
    op.drop_column("properties", "listing_status")
    op.drop_column("properties", "property_type")
    op.drop_column("properties", "square_feet")
    op.drop_column("properties", "bathrooms")
    op.drop_column("properties", "bedrooms")
    op.drop_column("properties", "price")
    op.drop_column("properties", "zip_code")
    op.drop_column("properties", "state")
    op.drop_column("properties", "city")
    op.drop_column("properties", "address")
    op.drop_column("properties", "description")
    op.drop_column("properties", "source_url")
    op.drop_column("properties", "source")
    op.drop_column("properties", "external_id")
