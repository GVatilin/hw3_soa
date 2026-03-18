from datetime import date

from fastapi import APIRouter, Depends, Query

from booking_service.app.deps import get_flight_client
from booking_service.app.grpc.client import FlightServiceClient
from booking_service.app.grpc.errors import raise_http_from_rpc_error
from booking_service.app.schemas.flight import FlightResponse

router = APIRouter(tags=["Flights"])


@router.get("/flights", response_model=list[FlightResponse])
def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: date | None = Query(None),
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    try:
        items = flight_client.search_flights(origin.upper(), destination.upper(), date)
        return [FlightResponse.model_validate(item.__dict__) for item in items]
    except Exception as exc:
        raise_http_from_rpc_error(exc)


@router.get("/flights/{flight_id}", response_model=FlightResponse)
def get_flight(
    flight_id: str,
    flight_client: FlightServiceClient = Depends(get_flight_client),
):
    try:
        item = flight_client.get_flight(flight_id)
        return FlightResponse.model_validate(item.__dict__)
    except Exception as exc:
        raise_http_from_rpc_error(exc)
