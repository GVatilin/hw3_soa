import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def _default_serializer(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Type {type(value)!r} is not JSON serializable")


class FlightCache:
    def __init__(self, redis_client, ttl_seconds: int) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def flight_key(flight_id: str) -> str:
        return f"flight:{flight_id}"

    @staticmethod
    def search_key(origin: str, destination: str, departure_date: date | None) -> str:
        suffix = departure_date.isoformat() if departure_date else "all"
        return f"search:{origin}:{destination}:{suffix}"

    def get_flight(self, flight_id: str) -> dict[str, Any] | None:
        key = self.flight_key(flight_id)
        data = self.redis.get(key)
        if data is None:
            logger.info("cache miss: %s", key)
            return None
        logger.info("cache hit: %s", key)
        return json.loads(data)

    def set_flight(self, flight_id: str, payload: dict[str, Any]) -> None:
        key = self.flight_key(flight_id)
        self.redis.setex(key, self.ttl_seconds, json.dumps(payload, default=_default_serializer))

    def get_search(self, origin: str, destination: str, departure_date: date | None) -> list[dict[str, Any]] | None:
        key = self.search_key(origin, destination, departure_date)
        data = self.redis.get(key)
        if data is None:
            logger.info("cache miss: %s", key)
            return None
        logger.info("cache hit: %s", key)
        return json.loads(data)

    def set_search(
        self, origin: str, destination: str, departure_date: date | None, payload: list[dict[str, Any]]
    ) -> None:
        key = self.search_key(origin, destination, departure_date)
        self.redis.setex(key, self.ttl_seconds, json.dumps(payload, default=_default_serializer))

    def invalidate_flight(self, flight_id: str) -> None:
        self.redis.delete(self.flight_key(flight_id))

    def invalidate_searches(self) -> None:
        keys = list(self.redis.scan_iter(match="search:*", count=500))
        if keys:
            self.redis.delete(*keys)
