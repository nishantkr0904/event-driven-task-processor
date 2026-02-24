"""
shared/schemas.py
Pydantic models shared between producer and worker services.
"""
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
import uuid


class TaskPayload(BaseModel):
    """Represents a task message published to RabbitMQ."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str  # e.g. "send_email", "resize_image", "process_payment"
    payload: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    max_retries: Optional[int] = None  # Overrides ENV default if set

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "task_type": "send_email",
                "payload": {"recipient": "user@example.com", "subject": "Welcome"},
                "retry_count": 0,
                "created_at": "2026-02-24T12:00:00",
            }
        }


class TaskResponse(BaseModel):
    """API response returned after publishing a task."""
    task_id: str
    status: str  # "queued"
    message: str
    created_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    timestamp: str
