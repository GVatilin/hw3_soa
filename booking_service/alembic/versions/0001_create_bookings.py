"""create bookings table

Revision ID: 0001_create_bookings
Revises:
Create Date: 2026-03-18 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_create_bookings"
down_revision = None
branch_labels = None
depends_on = None


booking_status = sa.Enum("CONFIRMED", "CANCELLED", name="booking_status")


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("flight_id", sa.String(length=36), nullable=False),
        sa.Column("passenger_name", sa.String(length=255), nullable=False),
        sa.Column("passenger_email", sa.String(length=255), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("seat_count > 0", name="ck_bookings_seat_count_positive"),
        sa.CheckConstraint("total_price > 0", name="ck_bookings_total_price_positive"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_flight_id", "bookings", ["flight_id"])
    op.create_index("ix_bookings_status", "bookings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_flight_id", table_name="bookings")
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_table("bookings")
