"""
worker/app/idempotency.py
Redis-backed idempotency checks for task deduplication.

Logic:
  1. Check if task_id key exists in Redis → skip if true
  2. After successful processing → SET task_id with TTL
"""
import redis
from worker.app.config import get_settings
from worker.app.logging_config import logger

settings = get_settings()

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
    return _redis_client


def _key(task_id: str) -> str:
    return f"task:processed:{task_id}"


def is_duplicate(task_id: str) -> bool:
    """Return True if this task_id has already been processed."""
    client = get_redis()
    exists = client.exists(_key(task_id))
    if exists:
        logger.info(
            "Duplicate task detected — skipping",
            extra={"task_id": task_id, "status": "duplicate_skipped"},
        )
    return bool(exists)


def mark_processed(task_id: str) -> None:
    """Record task_id in Redis with a TTL to prevent future duplicate processing."""
    client = get_redis()
    client.setex(
        name=_key(task_id),
        time=settings.REDIS_TASK_TTL,
        value="processed",
    )
    logger.info(
        "Task marked as processed in Redis",
        extra={
            "task_id": task_id,
            "ttl_seconds": settings.REDIS_TASK_TTL,
            "status": "idempotency_stored",
        },
    )
