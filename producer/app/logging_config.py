"""
producer/app/logging_config.py
Structured JSON logging configuration for the Producer service.
"""
import logging
import json
import sys
from datetime import datetime
from producer.app.config import get_settings

settings = get_settings()


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON log lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": settings.SERVICE_NAME,
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        # Merge any extra fields passed in
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg",
                "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName",
            ):
                log_entry[key] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> logging.Logger:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logging.root.setLevel(log_level)
    logging.root.handlers = [handler]
    return logging.getLogger(settings.SERVICE_NAME)


logger = setup_logging()
