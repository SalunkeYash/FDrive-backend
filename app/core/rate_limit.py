"""Simple sliding-window rate limiter (Redis when available, else memory)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.integrations.redis_client import get_redis

_memory_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_auth_rate_limit(request: Request) -> None:
    key = f"auth-rate:{client_ip(request)}"
    limit = settings.auth_rate_limit_per_minute
    window = 60
    if not _allow(key, limit, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many auth attempts. Try again in a minute.",
        )


def _allow(key: str, limit: int, window_seconds: int) -> bool:
    client = get_redis()
    now = time.time()
    if client is not None:
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        _, _, count, _ = pipe.execute()
        return int(count) <= limit

    with _lock:
        hits = _memory_hits[key]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        hits.append(now)
        return len(hits) <= limit
