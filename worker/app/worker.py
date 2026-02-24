"""
worker/app/worker.py
Worker service entrypoint — connects to RabbitMQ with retry and starts consuming.
"""
import time
import pika
import pika.exceptions
from worker.app.config import get_settings
from worker.app.logging_config import logger
from worker.app.consumer import process_message

settings = get_settings()

STARTUP_RETRY_ATTEMPTS = 10
STARTUP_RETRY_DELAY = 5  # seconds between connection attempts on startup


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


def _declare_infrastructure(channel) -> None:
    """Mirror the same infrastructure declarations as the producer."""
    # DLQ exchange + queue
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

    # Main task exchange
    channel.exchange_declare(
        exchange=settings.EXCHANGE_NAME,
        exchange_type=settings.EXCHANGE_TYPE,
        durable=True,
    )

    # Main task queue with DLQ binding
    channel.queue_declare(
        queue=settings.TASK_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": settings.DLQ_EXCHANGE},
    )
    channel.queue_bind(
        queue=settings.TASK_QUEUE,
        exchange=settings.EXCHANGE_NAME,
        routing_key=settings.ROUTING_KEY,
    )


def start_worker() -> None:
    """Connect to RabbitMQ (with startup retries) and begin consuming tasks."""
    for attempt in range(1, STARTUP_RETRY_ATTEMPTS + 1):
        try:
            logger.info(
                "Connecting to RabbitMQ",
                extra={"attempt": attempt, "host": settings.RABBITMQ_HOST, "status": "connecting"},
            )
            connection = _get_connection()
            channel = connection.channel()

            # Fair dispatch — one message at a time per worker
            channel.basic_qos(prefetch_count=1)

            _declare_infrastructure(channel)

            channel.basic_consume(
                queue=settings.TASK_QUEUE,
                on_message_callback=process_message,
                auto_ack=False,
            )

            logger.info(
                "Worker ready — waiting for tasks",
                extra={
                    "queue": settings.TASK_QUEUE,
                    "max_retries": settings.MAX_RETRIES,
                    "retry_base_delay": settings.RETRY_BASE_DELAY,
                    "status": "ready",
                },
            )
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as exc:
            logger.warning(
                "RabbitMQ not available yet — retrying",
                extra={"attempt": attempt, "error": str(exc), "retry_in_seconds": STARTUP_RETRY_DELAY},
            )
            if attempt == STARTUP_RETRY_ATTEMPTS:
                logger.error(
                    "Exhausted RabbitMQ connection attempts — exiting",
                    extra={"attempts": STARTUP_RETRY_ATTEMPTS, "status": "fatal"},
                )
                raise
            time.sleep(STARTUP_RETRY_DELAY)

        except KeyboardInterrupt:
            logger.info("Worker stopped by user", extra={"status": "stopped"})
            break


if __name__ == "__main__":
    start_worker()
