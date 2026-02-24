"""
producer/app/routes.py
FastAPI route definitions for the Producer service.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from shared.schemas import TaskPayload, TaskResponse, HealthResponse
from producer.app.publisher import publish_task
from producer.app.logging_config import logger

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Service liveness probe."""
    return HealthResponse(
        status="ok",
        service="producer",
        timestamp=datetime.utcnow().isoformat(),
    )


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Tasks"],
    summary="Submit a new task",
    description=(
        "Publishes a task payload to the RabbitMQ exchange. "
        "The worker service will asynchronously consume and process it."
    ),
)
async def submit_task(task: TaskPayload):
    """
    Submit a task for asynchronous processing.

    - **task_type**: Logical category of the task (e.g. `send_email`)
    - **payload**: Arbitrary JSON body for the task
    - **task_id**: Auto-generated UUID (can be overridden for idempotency)
    """
    try:
        publish_task(task)
    except Exception as exc:
        logger.error(
            "Error publishing task via API",
            extra={"task_id": task.task_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to publish task: {exc}",
        )

    return TaskResponse(
        task_id=task.task_id,
        status="queued",
        message="Task successfully published to the queue.",
        created_at=task.created_at,
    )


@router.post(
    "/tasks/simulate-failure",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Tasks"],
    summary="Submit a task that will intentionally fail",
    description=(
        "Publishes a task of type `fail_task` which the worker will "
        "intentionally fail to demonstrate retry + DLQ behaviour."
    ),
)
async def submit_failing_task(task: TaskPayload):
    """Force a task failure to trigger the retry & DLQ mechanism."""
    task.task_type = "fail_task"
    try:
        publish_task(task)
    except Exception as exc:
        logger.error(
            "Error publishing failing task via API",
            extra={"task_id": task.task_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to publish task: {exc}",
        )

    return TaskResponse(
        task_id=task.task_id,
        status="queued",
        message="Failure-simulation task queued. Watch worker logs for retries and DLQ.",
        created_at=task.created_at,
    )
