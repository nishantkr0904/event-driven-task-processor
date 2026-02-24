"""
producer/app/main.py
FastAPI application entrypoint for the Producer service.
"""
from fastapi import FastAPI
from producer.app.routes import router
from producer.app.logging_config import logger

app = FastAPI(
    title="Event-Driven Task Processor — Producer",
    description=(
        "Producer microservice that accepts task requests via HTTP and "
        "publishes them to a RabbitMQ exchange for asynchronous processing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup():
    logger.info("Producer service starting up", extra={"status": "starting"})


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Producer service shutting down", extra={"status": "stopping"})
