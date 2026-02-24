# Event-Driven Distributed Task Processing System

A **production-ready**, event-driven distributed task processing system built with **Python, FastAPI, RabbitMQ, Redis, and Docker**. Demonstrates fault-tolerant architecture, exponential backoff retries, dead-letter queueing, Redis idempotency, structured JSON logging, and cloud-ready containerisation.

---

## 🏗️ Architecture

```
Client  ──►  FastAPI Producer  ──►  RabbitMQ Exchange  ──►  task_queue
                                                                 │
                                                         Worker Consumer
                                                                 │
                                             ┌───────────────────┤
                                             ▼                   ▼
                                        Redis (idempotency)  Task Handler
                                                                 │
                                          ┌──────────────────────┤
                                          ▼ (failure)            ▼ (success)
                                    Retry / DLQ            ACK + Redis SETEX
```

> See [architecture.md](architecture.md) for the full ASCII diagram, component breakdown, and design decisions.

---

## ✨ Key Features

| Feature | Implementation |
|---|---|
| **Event-driven architecture** | FastAPI → RabbitMQ exchange → task queue |
| **Exchange / queue separation** | `task_exchange` (direct) routes to `task_queue` |
| **Async worker** | Blocking AMQP consumer with `prefetch_count=1` |
| **Exponential backoff** | `delay = RETRY_BASE_DELAY ^ retry_count` |
| **Dead Letter Queue** | Messages exceeding `MAX_RETRIES` routed to `dlq_queue` |
| **Redis idempotency** | `task_id` checked and stored with 24 h TTL pre/post processing |
| **Structured JSON logging** | Every log line is machine-parseable JSON |
| **Env-based config** | All tunables via `.env` / environment variables |
| **Dockerised microservices** | Producer, Worker, RabbitMQ, Redis — all containerised |
| **docker-compose orchestration** | Single command local spin-up with health checks |

---

## 🗂️ Project Structure

```
event-driven-task-processor/
├── producer/
│   ├── app/
│   │   ├── main.py           # FastAPI app entrypoint
│   │   ├── routes.py         # API route definitions
│   │   ├── publisher.py      # RabbitMQ publish logic
│   │   ├── config.py         # Env-based configuration
│   │   └── logging_config.py # Structured JSON logger
│   ├── Dockerfile
│   └── requirements.txt
├── worker/
│   ├── app/
│   │   ├── worker.py         # Entrypoint + startup retry loop
│   │   ├── consumer.py       # AMQP callback + task dispatch
│   │   ├── retry_handler.py  # Exponential backoff + DLQ publish
│   │   ├── idempotency.py    # Redis idempotency check
│   │   ├── config.py         # Env-based configuration
│   │   └── logging_config.py # Structured JSON logger
│   ├── Dockerfile
│   └── requirements.txt
├── shared/
│   └── schemas.py            # Pydantic models (TaskPayload, TaskResponse)
├── docker-compose.yml
├── .env
├── .env.example
├── architecture.md
└── README.md
```

---

## 🚀 Run Locally

### Prerequisites
- Docker ≥ 24
- Docker Compose ≥ 2.x

### Start all services

```bash
git clone https://github.com/nishantkr0904/event-driven-task-processor.git
cd event-driven-task-processor

# Copy env template (defaults work out of the box)
cp .env.example .env

docker-compose up --build
```

Services available after startup:

| Service | URL |
|---|---|
| Producer API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| RabbitMQ UI | http://localhost:15672 (guest / guest) |
| Redis | localhost:6379 |

---

## 📡 API Examples

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```
```json
{"status": "ok", "service": "producer", "timestamp": "2026-02-24T12:00:00"}
```

### Submit a Task
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "send_email",
    "payload": {
      "recipient": "user@example.com",
      "subject": "Welcome to the platform!"
    }
  }'
```
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Task successfully published to the queue.",
  "created_at": "2026-02-24T12:00:00"
}
```

### Idempotent Re-submission (same task_id)
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "send_email",
    "payload": {"recipient": "user@example.com", "subject": "Welcome!"}
  }'
```
> Worker **detects the duplicate** via Redis and skips processing — no double execution.

### Simulate Failure → Retry → DLQ
```bash
curl -X POST http://localhost:8000/api/v1/tasks/simulate-failure \
  -H "Content-Type: application/json" \
  -d '{"task_type": "fail_task", "payload": {}}'
```
Watch the logs:
```bash
docker-compose logs -f worker
```
You will see:
1. Task received
2. Simulated failure logged
3. Retry attempts (with exponential sleep: 2 s → 4 s → 8 s)
4. After `MAX_RETRIES=3`, task published to **dead_letter_queue**

Inspect the DLQ in RabbitMQ Management UI → **Queues → dead_letter_queue**.

---

## ⚙️ Configuration Reference

All values are set in `.env` (or as Docker environment variables):

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `RABBITMQ_PORT` | `5672` | AMQP port |
| `RABBITMQ_USER` | `guest` | AMQP username |
| `RABBITMQ_PASSWORD` | `guest` | AMQP password |
| `EXCHANGE_NAME` | `task_exchange` | Main exchange name |
| `ROUTING_KEY` | `task.process` | Routing key |
| `TASK_QUEUE` | `task_queue` | Main task queue |
| `DLQ_EXCHANGE` | `dlq_exchange` | Dead-letter exchange |
| `DLQ_QUEUE` | `dead_letter_queue` | Dead-letter queue |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_TASK_TTL` | `86400` | TTL (s) for idempotency keys |
| `MAX_RETRIES` | `3` | Max retry attempts before DLQ |
| `RETRY_BASE_DELAY` | `2.0` | Base delay for backoff (s) |

---

## 🔄 Retry & DLQ Explained

When a task handler raises an exception:

```
Attempt 1 → fail → sleep 2^1 = 2s  → re-queue
Attempt 2 → fail → sleep 2^2 = 4s  → re-queue
Attempt 3 → fail → sleep 2^3 = 8s  → re-queue
Attempt 4 → fail → MAX_RETRIES exceeded → DLQ
```

The original message is **ACK'd** immediately so it doesn't block the queue. The worker manually re-publishes the task with an incremented `retry_count` field baked into the JSON body.

---

## 🔁 Idempotency Explained

Every task carries a `task_id` (UUID). Before processing:
1. Worker checks `EXISTS task:processed:<task_id>` in Redis
2. If **found** → ACK the message and skip (no double processing)
3. If **not found** → process the task, then `SETEX task:processed:<task_id> 86400 "processed"`

This protects against:
- Network re-deliveries
- Consumer restarts
- Producer retry duplicates

---

## ☁️ Deploy on AWS EC2

```bash
# 1. Launch an EC2 instance (Ubuntu 22.04, t2.micro+)
# 2. SSH in and install Docker
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu && newgrp docker

# 3. Clone and run
git clone https://github.com/nishantkr0904/event-driven-task-processor.git
cd event-driven-task-processor
cp .env.example .env
docker compose up -d --build

# 4. Open Security Group ports: 8000 (API), 15672 (RabbitMQ UI)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| API / Producer | Python 3.11 + FastAPI + Uvicorn |
| Message Broker | RabbitMQ 3.12 (AMQP) |
| Idempotency Store | Redis 7.2 |
| Worker | Python 3.11 + Pika |
| Configuration | pydantic-settings |
| Logging | Custom JSON formatter (stdlib `logging`) |
| Containerisation | Docker + Docker Compose 3.9 |

---

## 📄 License

MIT License
