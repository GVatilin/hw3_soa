from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from flight_service.app.db.models import Flight, FlightStatus, SeatReservation, SeatReservationStatus
from flight_service.app.repositories.flights import FlightRepository
from flight_service.app.repositories.reservations import SeatReservationRepository
from flight_service.app.services.cache import FlightCache
from flight_service.app.services.exceptions import (
    FlightNotFoundError,
    InvalidReservationStateError,
    NotEnoughSeatsError,
    ReservationNotFoundError,
    ValidationError,
)


@dataclass
class FlightView:
    id: str
    flight_number: str
    airline_code: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    available_seats: int
    price: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ReservationView:
    id: str
    booking_id: str
    flight_id: str
    seat_count: int
    status: str


class FlightOperationsService:
    def __init__(self, db: Session, cache: FlightCache) -> None:
        self.db = db
        self.cache = cache
        self.flights = FlightRepository(db)
        self.reservations = SeatReservationRepository(db)

    @staticmethod
    def _serialize_flight(flight: Flight) -> dict:
        return {
            "id": flight.id,
            "flight_number": flight.flight_number,
            "airline_code": flight.airline_code,
            "origin": flight.origin,
            "destination": flight.destination,
            "departure_time": flight.departure_time,
            "arrival_time": flight.arrival_time,
            "total_seats": flight.total_seats,
            "available_seats": flight.available_seats,
            "price": flight.price,
            "status": flight.status.value,
            "created_at": flight.created_at,
            "updated_at": flight.updated_at,
        }

    @staticmethod
    def _view_from_payload(payload: dict) -> FlightView:
        return FlightView(
            id=payload["id"],
            flight_number=payload["flight_number"],
            airline_code=payload["airline_code"],
            origin=payload["origin"],
            destination=payload["destination"],
            departure_time=datetime.fromisoformat(payload["departure_time"]),
            arrival_time=datetime.fromisoformat(payload["arrival_time"]),
            total_seats=payload["total_seats"],
            available_seats=payload["available_seats"],
            price=Decimal(payload["price"]),
            status=payload["status"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
        )

    @staticmethod
    def _view_from_model(flight: Flight) -> FlightView:
        return FlightView(**FlightOperationsService._serialize_flight(flight))

    @staticmethod
    def _reservation_view(reservation: SeatReservation) -> ReservationView:
        return ReservationView(
            id=reservation.id,
            booking_id=reservation.booking_id,
            flight_id=reservation.flight_id,
            seat_count=reservation.seat_count,
            status=reservation.status.value,
        )

    def search_flights(self, origin: str, destination: str, departure_date: date | None) -> list[FlightView]:
        origin = origin.upper().strip()
        destination = destination.upper().strip()

        if len(origin) != 3 or len(destination) != 3:
            raise ValidationError("origin and destination must be 3-letter IATA codes")
        if origin == destination:
            raise ValidationError("origin and destination must differ")

        cached = self.cache.get_search(origin, destination, departure_date)
        if cached is not None:
            return [self._view_from_payload(item) for item in cached]

        items = self.flights.search_scheduled(origin, destination, departure_date)
        payload = [self._serialize_flight(item) for item in items]
        self.cache.set_search(origin, destination, departure_date, payload)
        return [self._view_from_model(item) for item in items]

    def get_flight(self, flight_id: str) -> FlightView:
        if not flight_id:
            raise ValidationError("flight_id is required")

        cached = self.cache.get_flight(flight_id)
        if cached is not None:
            return self._view_from_payload(cached)

        flight = self.flights.get_by_id(flight_id)
        if flight is None:
            raise FlightNotFoundError("Flight not found")

        payload = self._serialize_flight(flight)
        self.cache.set_flight(flight_id, payload)
        return self._view_from_model(flight)

    def reserve_seats(self, flight_id: str, booking_id: str, seat_count: int) -> ReservationView:
        if seat_count <= 0:
            raise ValidationError("seat_count must be > 0")
        if not flight_id or not booking_id:
            raise ValidationError("flight_id and booking_id are required")

        with self.db.begin():
            existing = self.reservations.lock_by_booking_id(booking_id)
            if existing is not None:
                if existing.status == SeatReservationStatus.ACTIVE:
                    if existing.flight_id == flight_id and existing.seat_count == seat_count:
                        return self._reservation_view(existing)
                    raise InvalidReservationStateError("booking_id already exists with different reservation payload")
                raise InvalidReservationStateError("reservation exists but is not active")

            flight = self.flights.lock_by_id(flight_id)
            if flight is None:
                raise FlightNotFoundError("Flight not found")

            if flight.status != FlightStatus.SCHEDULED:
                raise InvalidReservationStateError("Only SCHEDULED flights can be reserved")

            if flight.available_seats < seat_count:
                raise NotEnoughSeatsError("Not enough available seats")

            flight.available_seats -= seat_count

            reservation = SeatReservation(
                id=str(uuid.uuid4()),
                booking_id=booking_id,
                flight_id=flight_id,
                seat_count=seat_count,
                status=SeatReservationStatus.ACTIVE,
            )
            self.db.add(reservation)
            self.db.add(flight)

        self.cache.invalidate_flight(flight_id)
        self.cache.invalidate_searches()
        return self._reservation_view(reservation)

    def release_reservation(self, booking_id: str) -> ReservationView:
        if not booking_id:
            raise ValidationError("booking_id is required")

        with self.db.begin():
            reservation = self.reservations.lock_by_booking_id(booking_id)
            if reservation is None:
                raise ReservationNotFoundError("Reservation not found")

            if reservation.status != SeatReservationStatus.ACTIVE:
                raise InvalidReservationStateError("Reservation is not ACTIVE")

            flight = self.flights.lock_by_id(reservation.flight_id)
            if flight is None:
                raise FlightNotFoundError("Flight not found")

            flight.available_seats += reservation.seat_count
            reservation.status = SeatReservationStatus.RELEASED

            self.db.add(flight)
            self.db.add(reservation)

        self.cache.invalidate_flight(reservation.flight_id)
        self.cache.invalidate_searches()
        return self._reservation_view(reservation)
