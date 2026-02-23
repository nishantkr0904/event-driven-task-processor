# Event-Driven Distributed Task Processing System

A production-style distributed task processing system built using **Python, RabbitMQ, Redis, and Docker**, designed to demonstrate event-driven architecture, fault tolerance, idempotency, and cloud deployment simulation.

---

## 🚀 Architecture Overview

Producer (FastAPI) → RabbitMQ → Worker Service → Redis (Idempotency Store)

* Producers publish tasks to a message queue.
* Workers consume tasks asynchronously.
* Retry logic with exponential backoff ensures reliability.
* Idempotent task handling prevents duplicate processing.
* Structured JSON logging improves observability.
* Fully containerized with Docker.
* Designed for EC2-style cloud deployment simulation.

---

## 🔧 Tech Stack

* Python
* FastAPI
* RabbitMQ
* Redis
* Docker & Docker Compose
* Structured Logging
* Environment-based Configuration

---

## ⚙️ Key Features

* Event-driven asynchronous processing
* Message queue decoupling
* Exponential retry mechanism
* Dead Letter Queue handling
* Idempotent task execution
* Secure environment-based configuration
* Cloud-ready container deployment

---

## 🐳 Run Locally

```bash
docker-compose up --build
```

API will be available at:

```
http://localhost:8000
```

---

## ☁️ Cloud Deployment Simulation

Designed for deployment on:

* AWS EC2
* Any Linux VM
* Docker-supported cloud environment

---

## 📚 Why This Project?

This project demonstrates:

* Distributed systems thinking
* Fault-tolerant architecture design
* Message-based decoupling
* Production-style logging & configuration
* Containerized microservices setup

---

## 📄 License

MIT License
