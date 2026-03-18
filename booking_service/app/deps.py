from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from booking_service.app.db.session import SessionLocal
from booking_service.app.grpc.client import FlightServiceClient


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_flight_client(request: Request) -> FlightServiceClient:
    return request.app.state.flight_client
