import logging
from concurrent import futures

import grpc

import flight_service_pb2_grpc as flight_pb2_grpc
from flight_service.app.core.config import Settings
from flight_service.app.grpc.interceptors import ApiKeyServerInterceptor
from flight_service.app.grpc.servicer import FlightServiceServicer
from flight_service.app.services.cache import FlightCache

logger = logging.getLogger(__name__)


class GrpcServerController:
    def __init__(self, settings: Settings, cache: FlightCache) -> None:
        self.settings = settings
        self.cache = cache
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=settings.grpc_server_workers),
            interceptors=[ApiKeyServerInterceptor(settings.grpc_api_key)],
        )
        flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServiceServicer(cache), self.server)
        self.server.add_insecure_port(f"[::]:{settings.grpc_port}")

    def start(self) -> None:
        self.server.start()
        logger.info("Flight gRPC server started on port %s", self.settings.grpc_port)

    def stop(self) -> None:
        logger.info("Stopping Flight gRPC server")
        self.server.stop(grace=5)
