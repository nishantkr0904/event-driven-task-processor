"""
worker/app/consumer.py
Core task processing logic and RabbitMQ message callback.

Responsibilities:
  1. Deserialize the incoming TaskPayload message
  2. Idempotency check via Redis
  3. Dispatch to task handler based on task_type
  4. On success  → ack + mark_processed in Redis
  5. On failure  → nack (no requeue) + call retry_handler
"""
import json
import pika
import pika.adapters.blocking_connection
from shared.schemas import TaskPayload
from worker.app.config import get_settings
from worker.app.logging_config import logger
from worker.app.idempotency import is_duplicate, mark_processed
from worker.app.retry_handler import handle_failure

settings = get_settings()


# ---------------------------------------------------------------------------
# Task handlers — plug new task_type handlers here
# ---------------------------------------------------------------------------

def _handle_send_email(task: TaskPayload) -> None:
    logger.info(
        "Processing send_email task",
        extra={"task_id": task.task_id, "payload": task.payload, "status": "processing"},
    )
    recipient = task.payload.get("recipient", "unknown")
    subject = task.payload.get("subject", "(no subject)")
    # Simulated work
    logger.info(
        "Email sent successfully",
        extra={"task_id": task.task_id, "recipient": recipient, "subject": subject, "status": "success"},
    )


def _handle_resize_image(task: TaskPayload) -> None:
    logger.info(
        "Processing resize_image task",
        extra={"task_id": task.task_id, "payload": task.payload, "status": "processing"},
    )
    logger.info(
        "Image resized successfully",
        extra={"task_id": task.task_id, "status": "success"},
    )


def _handle_process_payment(task: TaskPayload) -> None:
    logger.info(
        "Processing process_payment task",
        extra={"task_id": task.task_id, "payload": task.payload, "status": "processing"},
    )
    logger.info(
        "Payment processed successfully",
        extra={"task_id": task.task_id, "status": "success"},
    )


def _handle_fail_task(task: TaskPayload) -> None:
    """Intentionally raises to test retry / DLQ flow."""
    logger.warning(
        "Simulating task failure for retry/DLQ testing",
        extra={"task_id": task.task_id, "status": "simulated_failure"},
    )
    raise RuntimeError("Intentional failure — testing retry mechanism")


TASK_HANDLERS = {
    "send_email": _handle_send_email,
    "resize_image": _handle_resize_image,
    "process_payment": _handle_process_payment,
    "fail_task": _handle_fail_task,
}


# ---------------------------------------------------------------------------
# RabbitMQ message callback
# ---------------------------------------------------------------------------

def process_message(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    """Callback invoked for each message consumed from the task queue."""
    try:
        raw = json.loads(body)
        task = TaskPayload(**raw)
    except Exception as exc:
        logger.error(
            "Failed to deserialize message — sending to DLQ",
            extra={"raw_body": body.decode(errors="replace"), "error": str(exc), "status": "deserialization_error"},
        )
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    logger.info(
        "Task received",
        extra={
            "task_id": task.task_id,
            "task_type": task.task_type,
            "retry_count": task.retry_count,
            "status": "received",
        },
    )

    # ── Idempotency check ────────────────────────────────────────────────────
    if is_duplicate(task.task_id):
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    # ── Dispatch ─────────────────────────────────────────────────────────────
    handler = TASK_HANDLERS.get(task.task_type)
    if handler is None:
        logger.warning(
            "Unknown task_type — discarding",
            extra={"task_id": task.task_id, "task_type": task.task_type, "status": "unknown_task_type"},
        )
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        handler(task)
        mark_processed(task.task_id)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(
            "Task completed successfully",
            extra={"task_id": task.task_id, "task_type": task.task_type, "status": "completed"},
        )
    except Exception as exc:
        # ACK the original message (we manually handle retry/DLQ)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        handle_failure(task, exc)
