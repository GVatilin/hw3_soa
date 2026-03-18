from redis import Redis
from redis.sentinel import Sentinel

from flight_service.app.core.config import Settings


def build_redis_client(settings: Settings) -> Redis:
    if settings.redis_mode.lower() == "sentinel":
        sentinel = Sentinel(settings.sentinel_nodes, socket_timeout=0.5)
        return sentinel.master_for(
            service_name=settings.redis_sentinel_service_name,
            socket_timeout=0.5,
            decode_responses=True,
        )

    return Redis.from_url(settings.redis_url, decode_responses=True)
