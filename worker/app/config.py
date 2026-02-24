"""
worker/app/config.py
Environment-based configuration for the Worker service.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class WorkerSettings(BaseSettings):
    # Service identity
    SERVICE_NAME: str = "worker"
    LOG_LEVEL: str = "INFO"

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"

    # Exchange / Queue names (must match producer)
    EXCHANGE_NAME: str = "task_exchange"
    EXCHANGE_TYPE: str = "direct"
    ROUTING_KEY: str = "task.process"
    TASK_QUEUE: str = "task_queue"
    DLQ_QUEUE: str = "dead_letter_queue"
    DLQ_EXCHANGE: str = "dlq_exchange"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_TASK_TTL: int = 86400  # seconds; how long to remember a processed task_id

    # Retry policy
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 2.0  # seconds; actual delay = base ^ retry_count

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> WorkerSettings:
    return WorkerSettings()
