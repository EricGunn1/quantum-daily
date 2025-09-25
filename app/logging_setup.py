# app/logging_setup.py
import logging
from logging.config import dictConfig
import contextvars
import os

# Per-request correlation ID
request_id_var = contextvars.ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True

def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIdFilter},
        },
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | "
                    "%(message)s (%(filename)s:%(lineno)d)"
                )
            },
            # Uvicorn access logs can keep their own short format if you prefer
            "uvicorn_access": {"format": "%(asctime)s | %(levelname)s | %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["request_id"],
            },
            "uvicorn_console": {
                "class": "logging.StreamHandler",
                "formatter": "uvicorn_access",
            },
        },
        "loggers": {
            # Your app
            "quantum_daily": {"handlers": ["console"], "level": level, "propagate": False},
            # Make child loggers inherit
            "quantum_daily.*": {"handlers": ["console"], "level": level, "propagate": False},

            # APScheduler logs
            "apscheduler": {"handlers": ["console"], "level": "INFO", "propagate": False},

            # Uvicorn/fastapi
            "uvicorn.error": {"handlers": ["uvicorn_console"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["uvicorn_console"], "level": "INFO", "propagate": False},
        },
        "root": {"handlers": ["console"], "level": level},
    })

# Convenience logger for app modules
def get_logger(name: str = "quantum_daily"):
    return logging.getLogger(name)
