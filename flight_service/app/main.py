from contextlib import asynccontextmanager

from fastapi import FastAPI

from flight_service.app.core.config import get_settings
from flight_service.app.core.logging import configure_logging
from flight_service.app.grpc.server import GrpcServerController
from flight_service.app.services.cache import FlightCache
from flight_service.app.services.redis_client import build_redis_client

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = build_redis_client(settings)
    cache = FlightCache(redis_client, ttl_seconds=settings.cache_ttl_seconds)
    grpc_server = GrpcServerController(settings, cache)

    app.state.redis = redis_client
    app.state.grpc_server = grpc_server

    grpc_server.start()
    yield
    grpc_server.stop()


app = FastAPI(
    title="Flight Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "flight-service"}
