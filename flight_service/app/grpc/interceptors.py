import logging

import grpc
from google.rpc import code_pb2, error_details_pb2, status_pb2
from grpc_status import rpc_status

logger = logging.getLogger(__name__)


class ApiKeyServerInterceptor(grpc.ServerInterceptor):
    def __init__(self, expected_api_key: str, header_name: str = "x-api-key") -> None:
        self.expected_api_key = expected_api_key
        self.header_name = header_name

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or [])
        received_api_key = metadata.get(self.header_name)

        if received_api_key == self.expected_api_key:
            return continuation(handler_call_details)

        logger.warning("Rejected unauthenticated gRPC request for %s", handler_call_details.method)
        handler = continuation(handler_call_details)

        def abort_unary_unary(request, context):
            status = status_pb2.Status(
                code=code_pb2.UNAUTHENTICATED,
                message="Invalid or missing API key",
            )
            error_info = error_details_pb2.ErrorInfo(
                reason="INVALID_API_KEY",
                domain="flight_service",
                metadata={"header": self.header_name},
            )
            status.details.add().Pack(error_info)
            context.abort_with_status(rpc_status.to_status(status))

        if handler is None:
            return grpc.unary_unary_rpc_method_handler(abort_unary_unary)

        return grpc.unary_unary_rpc_method_handler(
            abort_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
