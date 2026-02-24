# Event-Driven Task Processor — Architecture

## System Overview

This system implements a fully event-driven, fault-tolerant distributed task processor using a microservices architecture. Tasks are submitted via HTTP, decoupled through a message broker, and processed asynchronously by independent worker processes.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (HTTP)                               │
│              POST /api/v1/tasks  {task_type, payload}               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     PRODUCER (FastAPI :8000)                         │
│  • Validates payload (Pydantic)                                      │
│  • Assigns task_id (UUID)                                            │
│  • Publishes to RabbitMQ exchange                                    │
│  • Returns 202 Accepted + task_id                                    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  AMQP publish
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   RABBITMQ (task_exchange — direct)                  │
│                                                                      │
│   routing_key: task.process ──────────────► task_queue              │
│                              (x-dead-letter-exchange: dlq_exchange)  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  basic_consume (prefetch=1)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         WORKER SERVICE                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  1. Deserialize TaskPayload                                  │    │
│  └────────────────────────┬────────────────────────────────────┘    │
│                           │                                          │
│  ┌────────────────────────▼────────────────────────────────────┐    │
│  │  2. Idempotency Check (Redis)                                │    │
│  │     EXISTS task:processed:<task_id>  ──► YES → ACK & SKIP  │    │
│  └────────────────────────┬────────────────────────────────────┘    │
│                           │ NO                                       │
│  ┌────────────────────────▼────────────────────────────────────┐    │
│  │  3. Dispatch to task handler                                 │    │
│  │     (send_email | resize_image | process_payment | ...)      │    │
│  └──────────┬──────────────────────────┬───────────────────────┘    │
│             │ SUCCESS                  │ FAILURE                     │
│  ┌──────────▼──────────┐   ┌──────────▼──────────────────────┐     │
│  │ ACK + Redis SETEX   │   │  retry_count < MAX_RETRIES?      │     │
│  │ (task_id, TTL=24h)  │   │                                  │     │
│  └─────────────────────┘   │  YES → sleep(base^n) → re-queue  │     │
│                             │  NO  → publish to DLQ exchange   │     │
│                             └──────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
                               │  DLQ publish
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│               DEAD LETTER QUEUE (dlq_exchange → dlq_queue)           │
│  • Stores permanently failed tasks for manual inspection             │
│  • Visible in RabbitMQ Management UI (http://localhost:15672)        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Producer (FastAPI)
| File | Responsibility |
|---|---|
| `main.py` | Application entry, lifecycle hooks |
| `routes.py` | `/health`, `POST /tasks`, `POST /tasks/simulate-failure` |
| `publisher.py` | RabbitMQ connection, exchange/queue declaration, message publish |
| `config.py` | Pydantic-settings env-based configuration |
| `logging_config.py` | Structured JSON logging setup |

### Worker
| File | Responsibility |
|---|---|
| `worker.py` | Entrypoint; startup-retry loop; `channel.start_consuming()` |
| `consumer.py` | Message callback; dispatch; ack/nack |
| `idempotency.py` | Redis `EXISTS` + `SETEX` for task deduplication |
| `retry_handler.py` | Exponential backoff re-queue or DLQ publish |
| `config.py` | Pydantic-settings env-based configuration |
| `logging_config.py` | Structured JSON logging setup |

### Shared
| File | Responsibility |
|---|---|
| `schemas.py` | `TaskPayload`, `TaskResponse`, `HealthResponse` Pydantic models |

---

## Key Design Decisions

### Exchange vs Queue Separation
The **producer publishes to an exchange** (`task_exchange`, type `direct`) — not directly to a queue. The exchange routes messages to `task_queue` via the binding key `task.process`. This separation allows adding new consumers or routing rules without changing the producer.

### Idempotency via Redis
Every successfully processed `task_id` is stored in Redis with a 24-hour TTL. On receiving a message, the worker checks Redis before processing. Duplicate messages (e.g. from producer retries or network glitches) are safely skipped.

### Retry with Exponential Backoff
On processing failure:
- `retry_count` is incremented inside the `TaskPayload`
- Worker sleeps `RETRY_BASE_DELAY ^ retry_count` seconds
- Task is re-published to the main queue
- After `MAX_RETRIES` failures, the task is routed to the DLQ

```
Attempt 1 → fail → sleep 2s  → retry
Attempt 2 → fail → sleep 4s  → retry
Attempt 3 → fail → sleep 8s  → retry
Attempt 4 → fail → → → DLQ
```

### Dead Letter Queue
The `task_queue` is declared with `x-dead-letter-exchange: dlq_exchange`. The `dlq_queue` is bound to `dlq_exchange` (fanout). All messages that exceed retries are explicitly published to the DLQ for manual inspection or replay.

### Structured JSON Logging
Every log line across both services is a valid JSON object with mandatory fields:
```json
{
  "timestamp": "2026-02-24T12:00:00",
  "service": "worker",
  "level": "INFO",
  "event": "Task completed successfully",
  "task_id": "uuid...",
  "status": "completed"
}
```

---

## Data Flow Summary

```
Client POST /api/v1/tasks
  → Producer validates + assigns task_id
    → Published to task_exchange (routing_key: task.process)
      → Delivered to task_queue
        → Worker receives (prefetch=1)
          → Redis idempotency check
            → Handler dispatch (send_email, resize_image, etc.)
              → [SUCCESS] ACK + store task_id in Redis
              → [FAILURE] ACK + retry with backoff
                → [MAX RETRIES EXCEEDED] publish to DLQ
```
