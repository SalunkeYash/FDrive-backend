"""Redis helpers with graceful fallback for local/tests."""

from __future__ import annotations

from functools import lru_cache

import redis

from dependencies.config import settings


@lru_cache
def get_redis() -> redis.Redis | None:
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
        )
        client.ping()
        return client
    except Exception:
        return None
