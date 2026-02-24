"""
worker/app/retry_handler.py
Exponential backoff retry logic and Dead Letter Queue publisher.

Flow:
  - On task failure: increment retry_count
  - If retry_count < MAX_RETRIES: sleep(base_delay ^ retry_count) then re-publish to task queue
  - If retry_count >= MAX_RETRIES: publish to DLQ exchange for manual inspection
"""
import time
import pika
import pika.exceptions
from shared.schemas import TaskPayload
from worker.app.config import get_settings
from worker.app.logging_config import logger

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


def handle_failure(task: TaskPayload, error: Exception) -> None:
    """
    Called when a task raises an exception during processing.

    Increments retry_count and either:
      a) re-queues with exponential backoff delay, or
      b) sends to DLQ if max retries exceeded.
    """
    max_retries = task.max_retries if task.max_retries is not None else settings.MAX_RETRIES
    task.retry_count += 1

    if task.retry_count <= max_retries:
        delay = settings.RETRY_BASE_DELAY ** task.retry_count
        logger.warning(
            "Task failed — scheduling retry",
            extra={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "retry_count": task.retry_count,
                "max_retries": max_retries,
                "delay_seconds": delay,
                "error": str(error),
                "status": "retrying",
            },
        )
        time.sleep(delay)
        _republish_task(task)
    else:
        logger.error(
            "Task exceeded max retries — sending to Dead Letter Queue",
            extra={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "retry_count": task.retry_count,
                "max_retries": max_retries,
                "error": str(error),
                "status": "dead_lettered",
            },
        )
        _publish_to_dlq(task)


def _republish_task(task: TaskPayload) -> None:
    """Re-publish the task to the main task exchange for another processing attempt."""
    connection = _get_connection()
    try:
        channel = connection.channel()
        channel.basic_publish(
            exchange=settings.EXCHANGE_NAME,
            routing_key=settings.ROUTING_KEY,
            body=task.model_dump_json().encode(),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=task.task_id,
            ),
        )
        logger.info(
            "Task re-queued for retry",
            extra={
                "task_id": task.task_id,
                "retry_count": task.retry_count,
                "status": "re_queued",
            },
        )
    finally:
        try:
            connection.close()
        except Exception:
            pass


def _publish_to_dlq(task: TaskPayload) -> None:
    """Publish the dead-lettered task directly to the DLQ exchange."""
    connection = _get_connection()
    try:
        channel = connection.channel()
        # Ensure DLQ exchange and queue exist
        channel.exchange_declare(
            exchange=settings.DLQ_EXCHANGE,
            exchange_type="fanout",
            durable=True,
        )
        channel.queue_declare(queue=settings.DLQ_QUEUE, durable=True)
        channel.queue_bind(
            queue=settings.DLQ_QUEUE,
            exchange=settings.DLQ_EXCHANGE,
            routing_key="",
        )
        channel.basic_publish(
            exchange=settings.DLQ_EXCHANGE,
            routing_key="",
            body=task.model_dump_json().encode(),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=task.task_id,
            ),
        )
        logger.error(
            "Task published to Dead Letter Queue",
            extra={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "retry_count": task.retry_count,
                "status": "dlq_published",
            },
        )
    finally:
        try:
            connection.close()
        except Exception:
            pass
