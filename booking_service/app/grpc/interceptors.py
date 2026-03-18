import logging
import threading
import time
from collections import deque
from collections import namedtuple
from enum import Enum
from typing import Sequence

import grpc

logger = logging.getLogger(__name__)


_ClientCallDetails = namedtuple(
    "_ClientCallDetails",
    ("method", "timeout", "metadata", "credentials", "wait_for_ready", "compression"),
)


class ClientCallDetails(_ClientCallDetails, grpc.ClientCallDetails):
    pass


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(RuntimeError):
    pass


class ApiKeyClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self, api_key: str, header_name: str = "x-api-key") -> None:
        self.api_key = api_key
        self.header_name = header_name

    def intercept_unary_unary(self, continuation, client_call_details, request):
        metadata = list(client_call_details.metadata or [])
        metadata.append((self.header_name, self.api_key))

        new_details = ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=getattr(client_call_details, "wait_for_ready", None),
            compression=getattr(client_call_details, "compression", None),
        )
        return continuation(new_details, request)


class CircuitBreakerInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout_seconds: int,
        failure_window_seconds: int,
        failure_codes: Sequence[grpc.StatusCode],
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_window_seconds = failure_window_seconds
        self.failure_codes = set(failure_codes)

        self._lock = threading.Lock()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._failure_timestamps: deque[float] = deque()
        self._opened_at = 0.0
        self._half_open_probe_in_flight = False

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    def _transition(self, new_state: CircuitBreakerState) -> None:
        if new_state != self._state:
            logger.warning("Circuit breaker transition: %s -> %s", self._state, new_state)
        self._state = new_state

    def _before_request(self) -> None:
        with self._lock:
            now = time.monotonic()

            if self._state == CircuitBreakerState.OPEN:
                if now - self._opened_at >= self.recovery_timeout_seconds:
                    self._transition(CircuitBreakerState.HALF_OPEN)
                    self._half_open_probe_in_flight = False
                else:
                    logger.warning("Circuit breaker blocked request in OPEN state")
                    raise CircuitBreakerOpenError("Flight Service circuit breaker is OPEN")

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_probe_in_flight:
                    logger.warning("Circuit breaker blocked extra request in HALF_OPEN state")
                    raise CircuitBreakerOpenError("Flight Service circuit breaker is HALF_OPEN")
                self._half_open_probe_in_flight = True
                logger.info("Circuit breaker allowing probe request in HALF_OPEN state")

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._half_open_probe_in_flight = False
            self._transition(CircuitBreakerState.CLOSED)

    def _on_failure(self, code: grpc.StatusCode) -> None:
        with self._lock:
            if code not in self.failure_codes:
                self._failure_count = 0
                self._half_open_probe_in_flight = False
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._transition(CircuitBreakerState.CLOSED)
                return

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_probe_in_flight = False
                self._opened_at = time.monotonic()
                self._transition(CircuitBreakerState.OPEN)
                return

            now = time.monotonic()
            self._failure_count += 1
            self._failure_timestamps.append(now)
            while self._failure_timestamps and now - self._failure_timestamps[0] > self.failure_window_seconds:
                self._failure_timestamps.popleft()

            if self._failure_count >= self.failure_threshold or len(self._failure_timestamps) >= self.failure_threshold:
                self._opened_at = now
                self._transition(CircuitBreakerState.OPEN)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        self._before_request()

        try:
            response = continuation(client_call_details, request)

            if isinstance(response, grpc.Future):
                exc = response.exception()
                if exc is None:
                    self._on_success()
                elif isinstance(exc, grpc.RpcError):
                    self._on_failure(exc.code())
                else:
                    with self._lock:
                        if self._state == CircuitBreakerState.HALF_OPEN:
                            self._half_open_probe_in_flight = False
            else:
                self._on_success()
            return response
        except grpc.RpcError as exc:
            self._on_failure(exc.code())
            raise
        except Exception:
            with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._half_open_probe_in_flight = False
            raise
