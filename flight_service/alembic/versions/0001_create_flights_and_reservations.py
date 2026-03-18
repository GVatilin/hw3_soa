"""create flights and reservations tables

Revision ID: 0001_create_flights
Revises:
Create Date: 2026-03-18 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_create_flights"
down_revision = None
branch_labels = None
depends_on = None


flight_status = sa.Enum("SCHEDULED", "DEPARTED", "CANCELLED", "COMPLETED", name="flight_status")
seat_reservation_status = sa.Enum("ACTIVE", "RELEASED", "EXPIRED", name="seat_reservation_status")


def upgrade() -> None:
    op.create_table(
        "flights",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("flight_number", sa.String(length=16), nullable=False),
        sa.Column("airline_code", sa.String(length=8), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_seats", sa.Integer(), nullable=False),
        sa.Column("available_seats", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", flight_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flight_number", "departure_date", name="uq_flights_number_departure_date"),
        sa.CheckConstraint("total_seats > 0", name="ck_flights_total_seats_positive"),
        sa.CheckConstraint("available_seats >= 0", name="ck_flights_available_seats_non_negative"),
        sa.CheckConstraint("available_seats <= total_seats", name="ck_flights_available_le_total"),
        sa.CheckConstraint("price > 0", name="ck_flights_price_positive"),
        sa.CheckConstraint("origin <> destination", name="ck_flights_route_not_same"),
    )
    op.create_index("ix_flights_route_date", "flights", ["origin", "destination", "departure_date"])
    op.create_index("ix_flights_status", "flights", ["status"])

    op.create_table(
        "seat_reservations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("booking_id", sa.String(length=36), nullable=False),
        sa.Column("flight_id", sa.String(length=36), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("status", seat_reservation_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["flight_id"], ["flights.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", name="uq_seat_reservations_booking_id"),
        sa.CheckConstraint("seat_count > 0", name="ck_seat_reservations_seat_count_positive"),
    )
    op.create_index("ix_seat_reservations_flight_id", "seat_reservations", ["flight_id"])
    op.create_index("ix_seat_reservations_status", "seat_reservations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_seat_reservations_status", table_name="seat_reservations")
    op.drop_index("ix_seat_reservations_flight_id", table_name="seat_reservations")
    op.drop_table("seat_reservations")

    op.drop_index("ix_flights_status", table_name="flights")
    op.drop_index("ix_flights_route_date", table_name="flights")
    op.drop_table("flights")
