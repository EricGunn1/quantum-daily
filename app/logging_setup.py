# app/logging_setup.py
import logging
from logging.config import dictConfig
from logging import LogRecord
from pathlib import Path
import contextvars
import os

# ---- Correlation ID (used by middleware) ----
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record: LogRecord) -> bool:
        # Attach the current request_id (or "-" if none) to every record
        record.request_id = request_id_var.get()
        return True

# ---- Paths & levels ----
BASE_DIR = Path(__file__).resolve().parents[1]  # project root (folder that contains 'app/')
LOG_DIR  = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def setup_logging() -> Path:
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
            "uvicorn_access": {
                "format": "%(asctime)s | %(levelname)s | %(message)s"
            },
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["request_id"],
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "standard",
                "filters": ["request_id"],
                "filename": str(LOG_FILE),
                "when": "midnight",
                "backupCount": 14,
                "encoding": "utf-8",
            },
            "uvicorn_console": {
                "class": "logging.StreamHandler",
                "formatter": "uvicorn_access",
            },
        },

        "loggers": {
            # Your app; children (quantum_daily.*) will inherit unless they override
            "quantum_daily":   {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": True},
            "quantum_daily.*": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": True},

            # APScheduler
            "apscheduler": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},

            # Uvicorn/Starlette (keep their own concise format, but also file)
            "uvicorn.error":  {"handlers": ["uvicorn_console", "file"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["uvicorn_console", "file"], "level": "INFO", "propagate": False},
        },

        # Root logger as a catch-all
        "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    })

    logging.getLogger("quantum_daily").info(f"Logging to: {LOG_FILE}")
    return LOG_FILE

def get_logger(name: str = "quantum_daily") -> logging.Logger:
    return logging.getLogger(name)
