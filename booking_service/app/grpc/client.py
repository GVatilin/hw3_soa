from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import logging
import time

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

import flight_service_pb2 as flight_pb2
import flight_service_pb2_grpc as flight_pb2_grpc
from booking_service.app.core.config import Settings
from booking_service.app.grpc.interceptors import (
    ApiKeyClientInterceptor,
    CircuitBreakerInterceptor,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)


@dataclass
class FlightDTO:
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
    created_at: datetime | None
    updated_at: datetime | None


class FlightServiceClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        base_channel = grpc.insecure_channel(settings.flight_service_target)
        intercepted = grpc.intercept_channel(
            base_channel,
            ApiKeyClientInterceptor(settings.grpc_api_key),
            CircuitBreakerInterceptor(
                failure_threshold=settings.circuit_breaker_failure_threshold,
                recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
                failure_window_seconds=settings.circuit_breaker_failure_window_seconds,
                failure_codes=tuple(settings.circuit_breaker_failure_statuses),
            ),
        )
        self.channel = intercepted
        self.stub = flight_pb2_grpc.FlightServiceStub(self.channel)

    def close(self) -> None:
        self.channel.close()

    def _should_retry(self, exc: grpc.RpcError) -> bool:
        return exc.code() in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}

    def _execute_with_retry(self, func):
        attempt = 0
        delay_ms = self.settings.grpc_backoff_base_ms

        while True:
            try:
                return func()
            except CircuitBreakerOpenError:
                raise
            except grpc.RpcError as exc:
                attempt += 1
                if not self._should_retry(exc) or attempt >= self.settings.grpc_max_retries:
                    raise

                logger.warning(
                    "Retrying gRPC call after %s (attempt %s/%s, backoff=%sms)",
                    exc.code().name,
                    attempt,
                    self.settings.grpc_max_retries,
                    delay_ms,
                )
                time.sleep(delay_ms / 1000)
                delay_ms *= 2

    @staticmethod
    def _date_to_timestamp(value: date) -> Timestamp:
        ts = Timestamp()
        ts.FromDatetime(datetime(value.year, value.month, value.day, tzinfo=timezone.utc))
        return ts

    @staticmethod
    def _timestamp_to_datetime(ts: Timestamp) -> datetime | None:
        if ts.seconds == 0 and ts.nanos == 0:
            return None
        return ts.ToDatetime(tzinfo=timezone.utc)

    @staticmethod
    def _map_flight(proto: flight_pb2.Flight) -> FlightDTO:
        return FlightDTO(
            id=proto.id,
            flight_number=proto.flight_number,
            airline_code=proto.airline_code,
            origin=proto.origin,
            destination=proto.destination,
            departure_time=FlightServiceClient._timestamp_to_datetime(proto.departure_time),
            arrival_time=FlightServiceClient._timestamp_to_datetime(proto.arrival_time),
            total_seats=proto.total_seats,
            available_seats=proto.available_seats,
            price=Decimal(proto.price),
            status=flight_pb2.FlightStatus.Name(proto.status),
            created_at=FlightServiceClient._timestamp_to_datetime(proto.created_at),
            updated_at=FlightServiceClient._timestamp_to_datetime(proto.updated_at),
        )

    def search_flights(self, origin: str, destination: str, departure_date: date | None = None) -> list[FlightDTO]:
        request = flight_pb2.SearchFlightsRequest(origin=origin, destination=destination)
        if departure_date:
            request.departure_date.CopyFrom(self._date_to_timestamp(departure_date))

        response = self._execute_with_retry(
            lambda: self.stub.SearchFlights(request, timeout=self.settings.grpc_timeout_seconds)
        )
        return [self._map_flight(item) for item in response.flights]

    def get_flight(self, flight_id: str) -> FlightDTO:
        request = flight_pb2.GetFlightRequest(flight_id=flight_id)
        response = self._execute_with_retry(
            lambda: self.stub.GetFlight(request, timeout=self.settings.grpc_timeout_seconds)
        )
        return self._map_flight(response)

    def reserve_seats(self, flight_id: str, booking_id: str, seat_count: int) -> None:
        request = flight_pb2.ReserveSeatsRequest(
            flight_id=flight_id,
            booking_id=booking_id,
            seat_count=seat_count,
        )
        self._execute_with_retry(
            lambda: self.stub.ReserveSeats(request, timeout=self.settings.grpc_timeout_seconds)
        )

    def release_reservation(self, booking_id: str) -> None:
        request = flight_pb2.ReleaseReservationRequest(booking_id=booking_id)
        self._execute_with_retry(
            lambda: self.stub.ReleaseReservation(request, timeout=self.settings.grpc_timeout_seconds)
        )
