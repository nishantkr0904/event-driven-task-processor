"""
producer/app/config.py
Environment-based configuration for the Producer service.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class ProducerSettings(BaseSettings):
    # Service identity
    SERVICE_NAME: str = "producer"
    LOG_LEVEL: str = "INFO"

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"

    # Exchange / Queue names
    EXCHANGE_NAME: str = "task_exchange"
    EXCHANGE_TYPE: str = "direct"
    ROUTING_KEY: str = "task.process"
    TASK_QUEUE: str = "task_queue"
    DLQ_QUEUE: str = "dead_letter_queue"
    DLQ_EXCHANGE: str = "dlq_exchange"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> ProducerSettings:
    return ProducerSettings()
