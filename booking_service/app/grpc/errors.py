import grpc
from fastapi import HTTPException, status
from google.rpc import error_details_pb2
from grpc_status import rpc_status

from booking_service.app.grpc.interceptors import CircuitBreakerOpenError


def _format_rpc_detail(exc: grpc.RpcError) -> str:
    code = exc.code()
    base = exc.details() or code.name
    parsed_status = rpc_status.from_call(exc)
    if parsed_status is None:
        return base

    for detail in parsed_status.details:
        error_info = error_details_pb2.ErrorInfo()
        if detail.Is(error_info.DESCRIPTOR):
            detail.Unpack(error_info)
            reason = error_info.reason.strip()
            if not reason:
                return base
            return f"{base} ({reason})"

    return base


def raise_http_from_rpc_error(exc: Exception) -> None:
    if isinstance(exc, CircuitBreakerOpenError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if isinstance(exc, grpc.RpcError):
        code = exc.code()
        detail = _format_rpc_detail(exc)

        if code == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        if code == grpc.StatusCode.FAILED_PRECONDITION:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        if code == grpc.StatusCode.UNAUTHENTICATED:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
        if code in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
