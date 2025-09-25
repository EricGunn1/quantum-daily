# app/lifespan.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .logging_setup import get_logger
from .store import init_db
from .scheduler import add_jobs, start_scheduler, shutdown_scheduler

logger = get_logger("quantum_daily.lifespan")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("APP STARTUP")
    init_db()

    if not getattr(app.state, "scheduler_started", False):
        logger.info("Registering scheduler jobs")
        add_jobs()
        start_scheduler()
        app.state.scheduler_started = True
        logger.info("Scheduler started")

    # Hand control to the application
    yield

    # ---- Shutdown ----
    logger.info("APP SHUTDOWN")
    if getattr(app.state, "scheduler_started", False):
        logger.info("Stopping scheduler")
        shutdown_scheduler(wait=False)
        app.state.scheduler_started = False
