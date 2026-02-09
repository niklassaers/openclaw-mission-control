"""RQ queue and Redis connection helpers for background workers."""

from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.config import settings


def get_redis() -> Redis:
    """Create a Redis client from configured settings."""
    return Redis.from_url(settings.redis_url)


def get_queue(name: str) -> Queue:
    """Return an RQ queue bound to the configured Redis connection."""
    return Queue(name, connection=get_redis())
