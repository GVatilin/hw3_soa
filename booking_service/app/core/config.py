from functools import lru_cache
from typing import Set

import grpc
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOOKING_", extra="ignore")

    app_port: int = 8000
    database_url: str
    flight_service_target: str = "flight-service:50051"
    grpc_timeout_seconds: int = 3
    grpc_max_retries: int = 3
    grpc_backoff_base_ms: int = 100
    grpc_api_key: str
    log_level: str = "INFO"

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 15
    circuit_breaker_failure_window_seconds: int = 30
    circuit_breaker_failure_codes: str = "UNAVAILABLE,DEADLINE_EXCEEDED"

    @property
    def circuit_breaker_failure_statuses(self) -> Set[grpc.StatusCode]:
        result: set[grpc.StatusCode] = set()
        for item in self.circuit_breaker_failure_codes.split(","):
            item = item.strip()
            if not item:
                continue
            result.add(getattr(grpc.StatusCode, item))
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
