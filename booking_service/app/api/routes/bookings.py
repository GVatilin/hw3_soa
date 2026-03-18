from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from booking_service.app.deps import get_db, get_flight_client
from booking_service.app.grpc.client import FlightServiceClient
from booking_service.app.schemas.booking import BookingListResponse, BookingResponse, CreateBookingRequest
from booking_service.app.services.bookings import BookingAppService

router = APIRouter(tags=["Bookings"])


@router.post("/bookings", response_model=BookingResponse, status_code=201)
def create_booking(
    payload: CreateBookingRequest,
    db: Session = Depends(get_db),
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    service = BookingAppService(db, flight_client)
    booking = service.create_booking(payload)
    return BookingResponse.model_validate(booking)


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    service = BookingAppService(db, flight_client)
    booking = service.get_booking(booking_id)
    return BookingResponse.model_validate(booking)


@router.get("/bookings", response_model=BookingListResponse)
def list_bookings(
    user_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    service = BookingAppService(db, flight_client)
    items = service.list_bookings(user_id)
    return BookingListResponse(items=[BookingResponse.model_validate(item) for item in items])


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    service = BookingAppService(db, flight_client)
    booking = service.cancel_booking(booking_id)
    return BookingResponse.model_validate(booking)
