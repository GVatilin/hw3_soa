from datetime import timezone

import grpc
from google.rpc import code_pb2, error_details_pb2, status_pb2
from google.protobuf.timestamp_pb2 import Timestamp
from grpc_status import rpc_status

import flight_service_pb2 as flight_pb2
import flight_service_pb2_grpc as flight_pb2_grpc
from flight_service.app.db.session import SessionLocal
from flight_service.app.services.cache import FlightCache
from flight_service.app.services.exceptions import (
    FlightNotFoundError,
    InvalidReservationStateError,
    NotEnoughSeatsError,
    ReservationNotFoundError,
    ValidationError,
)
from flight_service.app.services.flight_ops import FlightOperationsService


def dt_to_timestamp(value):
    ts = Timestamp()
    ts.FromDatetime(value.astimezone(timezone.utc))
    return ts


def flight_status_to_proto(value: str) -> int:
    return getattr(flight_pb2, value)


def reservation_status_to_proto(value: str) -> int:
    return getattr(flight_pb2, value)


def grpc_code_to_rpc_code(code: grpc.StatusCode) -> int:
    return getattr(code_pb2, code.name)


def abort_with_rich_status(
    context: grpc.ServicerContext,
    code: grpc.StatusCode,
    message: str,
    reason: str,
    metadata: dict[str, str] | None = None,
) -> None:
    status = status_pb2.Status(
        code=grpc_code_to_rpc_code(code),
        message=message,
    )
    error_info = error_details_pb2.ErrorInfo(
        reason=reason,
        domain="flight_service",
        metadata=metadata or {},
    )
    status.details.add().Pack(error_info)
    context.abort_with_status(rpc_status.to_status(status))


class FlightServiceServicer(flight_pb2_grpc.FlightServiceServicer):
    def __init__(self, cache: FlightCache) -> None:
        self.cache = cache

    def SearchFlights(self, request, context):
        db = SessionLocal()
        try:
            service = FlightOperationsService(db, self.cache)
            departure_date = request.departure_date.ToDatetime().date() if request.HasField("departure_date") else None
            flights = service.search_flights(request.origin, request.destination, departure_date)
            return flight_pb2.SearchFlightsResponse(
                flights=[
                    flight_pb2.Flight(
                        id=item.id,
                        flight_number=item.flight_number,
                        airline_code=item.airline_code,
                        origin=item.origin,
                        destination=item.destination,
                        departure_time=dt_to_timestamp(item.departure_time),
                        arrival_time=dt_to_timestamp(item.arrival_time),
                        total_seats=item.total_seats,
                        available_seats=item.available_seats,
                        price=str(item.price),
                        status=flight_status_to_proto(item.status),
                        created_at=dt_to_timestamp(item.created_at),
                        updated_at=dt_to_timestamp(item.updated_at),
                    )
                    for item in flights
                ]
            )
        except ValidationError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                str(exc),
                reason="VALIDATION_ERROR",
            )
        finally:
            db.close()

    def GetFlight(self, request, context):
        db = SessionLocal()
        try:
            service = FlightOperationsService(db, self.cache)
            item = service.get_flight(request.flight_id)
            return flight_pb2.Flight(
                id=item.id,
                flight_number=item.flight_number,
                airline_code=item.airline_code,
                origin=item.origin,
                destination=item.destination,
                departure_time=dt_to_timestamp(item.departure_time),
                arrival_time=dt_to_timestamp(item.arrival_time),
                total_seats=item.total_seats,
                available_seats=item.available_seats,
                price=str(item.price),
                status=flight_status_to_proto(item.status),
                created_at=dt_to_timestamp(item.created_at),
                updated_at=dt_to_timestamp(item.updated_at),
            )
        except ValidationError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                str(exc),
                reason="VALIDATION_ERROR",
                metadata={"flight_id": request.flight_id},
            )
        except FlightNotFoundError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.NOT_FOUND,
                str(exc),
                reason="FLIGHT_NOT_FOUND",
                metadata={"flight_id": request.flight_id},
            )
        finally:
            db.close()

    def ReserveSeats(self, request, context):
        db = SessionLocal()
        try:
            service = FlightOperationsService(db, self.cache)
            result = service.reserve_seats(
                flight_id=request.flight_id,
                booking_id=request.booking_id,
                seat_count=request.seat_count,
            )
            return flight_pb2.ReserveSeatsResponse(
                reservation_id=result.id,
                flight_id=result.flight_id,
                booking_id=result.booking_id,
                seat_count=result.seat_count,
                status=reservation_status_to_proto(result.status),
            )
        except ValidationError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                str(exc),
                reason="VALIDATION_ERROR",
                metadata={"flight_id": request.flight_id, "booking_id": request.booking_id},
            )
        except FlightNotFoundError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.NOT_FOUND,
                str(exc),
                reason="FLIGHT_NOT_FOUND",
                metadata={"flight_id": request.flight_id, "booking_id": request.booking_id},
            )
        except NotEnoughSeatsError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                str(exc),
                reason="NOT_ENOUGH_SEATS",
                metadata={"flight_id": request.flight_id, "booking_id": request.booking_id},
            )
        except InvalidReservationStateError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.FAILED_PRECONDITION,
                str(exc),
                reason="INVALID_RESERVATION_STATE",
                metadata={"flight_id": request.flight_id, "booking_id": request.booking_id},
            )
        finally:
            db.close()

    def ReleaseReservation(self, request, context):
        db = SessionLocal()
        try:
            service = FlightOperationsService(db, self.cache)
            result = service.release_reservation(request.booking_id)
            return flight_pb2.ReleaseReservationResponse(
                reservation_id=result.id,
                booking_id=result.booking_id,
                flight_id=result.flight_id,
                released_seats=result.seat_count,
                status=reservation_status_to_proto(result.status),
            )
        except ValidationError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                str(exc),
                reason="VALIDATION_ERROR",
                metadata={"booking_id": request.booking_id},
            )
        except ReservationNotFoundError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.NOT_FOUND,
                str(exc),
                reason="RESERVATION_NOT_FOUND",
                metadata={"booking_id": request.booking_id},
            )
        except FlightNotFoundError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.NOT_FOUND,
                str(exc),
                reason="FLIGHT_NOT_FOUND",
                metadata={"booking_id": request.booking_id},
            )
        except InvalidReservationStateError as exc:
            abort_with_rich_status(
                context,
                grpc.StatusCode.FAILED_PRECONDITION,
                str(exc),
                reason="INVALID_RESERVATION_STATE",
                metadata={"booking_id": request.booking_id},
            )
        finally:
            db.close()
