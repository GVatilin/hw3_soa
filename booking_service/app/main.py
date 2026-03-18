from contextlib import asynccontextmanager

from fastapi import FastAPI

from booking_service.app.api.routes.bookings import router as bookings_router
from booking_service.app.api.routes.flights import router as flights_router
from booking_service.app.core.config import get_settings
from booking_service.app.core.logging import configure_logging
from booking_service.app.grpc.client import FlightServiceClient

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.flight_client = FlightServiceClient(settings)
    yield
    app.state.flight_client.close()


app = FastAPI(
    title="Booking Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(flights_router)
app.include_router(bookings_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "booking-service"}
