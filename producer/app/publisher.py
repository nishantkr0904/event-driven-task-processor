"""
producer/app/publisher.py
RabbitMQ publisher — declares exchange, queues, DLQ binding, and publishes tasks.
"""
import json
import pika
import pika.exceptions
from producer.app.config import get_settings
from producer.app.logging_config import logger
from shared.schemas import TaskPayload

settings = get_settings()


def _get_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
    )
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        virtual_host=settings.RABBITMQ_VHOST,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )
    return pika.BlockingConnection(parameters)


def _declare_infrastructure(channel: pika.adapters.blocking_connection.BlockingChannel):
    """Idempotently declare exchange, DLQ exchange, DLQ queue, and main task queue."""
    # 1. Dead-letter exchange (fanout so DLQ queue gets everything)
    channel.exchange_declare(
        exchange=settings.DLQ_EXCHANGE,
        exchange_type="fanout",
        durable=True,
    )
    # 2. Dead-letter queue
    channel.queue_declare(queue=settings.DLQ_QUEUE, durable=True)
    channel.queue_bind(
        queue=settings.DLQ_QUEUE,
        exchange=settings.DLQ_EXCHANGE,
        routing_key="",
    )

    # 3. Main task exchange (direct)
    channel.exchange_declare(
        exchange=settings.EXCHANGE_NAME,
        exchange_type=settings.EXCHANGE_TYPE,
        durable=True,
    )

    # 4. Main task queue — with x-dead-letter-exchange pointing to DLQ exchange
    channel.queue_declare(
        queue=settings.TASK_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.DLQ_EXCHANGE,
        },
    )
    channel.queue_bind(
        queue=settings.TASK_QUEUE,
        exchange=settings.EXCHANGE_NAME,
        routing_key=settings.ROUTING_KEY,
    )


def publish_task(task: TaskPayload) -> None:
    """Publish a TaskPayload message to the main task exchange."""
    connection = _get_connection()
    try:
        channel = connection.channel()
        _declare_infrastructure(channel)

        body = task.model_dump_json().encode()
        channel.basic_publish(
            exchange=settings.EXCHANGE_NAME,
            routing_key=settings.ROUTING_KEY,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
                message_id=task.task_id,
            ),
        )
        logger.info(
            "Task published to RabbitMQ",
            extra={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": "queued",
                "exchange": settings.EXCHANGE_NAME,
            },
        )
    except pika.exceptions.AMQPError as exc:
        logger.error(
            "Failed to publish task",
            extra={"task_id": task.task_id, "error": str(exc)},
        )
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass
