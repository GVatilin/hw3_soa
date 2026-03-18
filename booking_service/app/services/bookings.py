from decimal import Decimal, ROUND_HALF_UP
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking_service.app.db.models import Booking, BookingStatus
from booking_service.app.grpc.client import FlightServiceClient
from booking_service.app.grpc.errors import raise_http_from_rpc_error
from booking_service.app.schemas.booking import CreateBookingRequest

logger = logging.getLogger(__name__)


class BookingAppService:
    def __init__(self, db: Session, flight_client: FlightServiceClient) -> None:
        self.db = db
        self.flight_client = flight_client

    def create_booking(self, payload: CreateBookingRequest) -> Booking:
        booking_id = str(uuid.uuid4())
        reservation_created = False

        try:
            flight = self.flight_client.get_flight(str(payload.flight_id))
            total_price = (flight.price * payload.seat_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            self.flight_client.reserve_seats(
                flight_id=str(payload.flight_id),
                booking_id=booking_id,
                seat_count=payload.seat_count,
            )
            reservation_created = True
        except Exception as exc:
            raise_http_from_rpc_error(exc)

        booking = Booking(
            id=booking_id,
            user_id=payload.user_id,
            flight_id=str(payload.flight_id),
            passenger_name=payload.passenger_name,
            passenger_email=str(payload.passenger_email),
            seat_count=payload.seat_count,
            total_price=total_price,
            status=BookingStatus.CONFIRMED,
        )

        try:
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            return booking
        except Exception:
            self.db.rollback()
            if reservation_created:
                try:
                    self.flight_client.release_reservation(booking_id)
                except Exception:
                    logger.exception("Compensation failed: could not release reservation for booking_id=%s", booking_id)
            raise

    def get_booking(self, booking_id: str) -> Booking:
        booking = self.db.get(Booking, booking_id)
        if booking is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return booking

    def list_bookings(self, user_id: str) -> list[Booking]:
        return list(
            self.db.execute(select(Booking).where(Booking.user_id == user_id).order_by(Booking.created_at.desc()))
            .scalars()
            .all()
        )

    def cancel_booking(self, booking_id: str) -> Booking:
        booking = self.db.get(Booking, booking_id)
        if booking is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking already cancelled")

        try:
            self.flight_client.release_reservation(booking_id)
        except Exception as exc:
            raise_http_from_rpc_error(exc)

        booking.status = BookingStatus.CANCELLED
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking
