from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FLIGHT_", extra="ignore")

    app_port: int = 8001
    grpc_port: int = 50051
    grpc_server_workers: int = 20
    database_url: str
    grpc_api_key: str
    log_level: str = "INFO"

    cache_ttl_seconds: int = 300
    redis_mode: str = "sentinel"
    redis_url: str = "redis://redis-master:6379/0"
    redis_sentinel_nodes: str = "redis-sentinel:26379"
    redis_sentinel_service_name: str = "mymaster"

    @property
    def sentinel_nodes(self) -> list[tuple[str, int]]:
        nodes: list[tuple[str, int]] = []
        for item in self.redis_sentinel_nodes.split(","):
            item = item.strip()
            if not item:
                continue
            host, port = item.split(":")
            nodes.append((host, int(port)))
        return nodes


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
