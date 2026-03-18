from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flight_service.app.db.base import Base


class FlightStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class SeatReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint("flight_number", "departure_date", name="uq_flights_number_departure_date"),
        CheckConstraint("total_seats > 0", name="ck_flights_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="ck_flights_available_seats_non_negative"),
        CheckConstraint("available_seats <= total_seats", name="ck_flights_available_le_total"),
        CheckConstraint("price > 0", name="ck_flights_price_positive"),
        CheckConstraint("origin <> destination", name="ck_flights_route_not_same"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_number: Mapped[str] = mapped_column(String(16), nullable=False)
    airline_code: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[FlightStatus] = mapped_column(
        SAEnum(FlightStatus, name="flight_status"), nullable=False, default=FlightStatus.SCHEDULED, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reservations: Mapped[list["SeatReservation"]] = relationship(
        back_populates="flight", cascade="all, delete-orphan"
    )


class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_seat_reservations_booking_id"),
        CheckConstraint("seat_count > 0", name="ck_seat_reservations_seat_count_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    flight_id: Mapped[str] = mapped_column(String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeatReservationStatus] = mapped_column(
        SAEnum(SeatReservationStatus, name="seat_reservation_status"),
        nullable=False,
        default=SeatReservationStatus.ACTIVE,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    flight: Mapped[Flight] = relationship(back_populates="reservations")
