# app/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import pytz

from .config import TIMEZONE, DEFAULT_SEND_HOUR
from .workflow import run_daily
from .logging_setup import get_logger

logger = get_logger("quantum_daily.scheduler")
scheduler = BackgroundScheduler()

def _job_listener(event):
    if event.exception:
        # APScheduler already captures traceback; this logs it via our logger too.
        logger.exception(
            "JOB_ERROR",
            extra={"handled": False, "job_id": event.job_id, "run_time": str(event.scheduled_run_time)}
        )
    else:
        logger.info(
            "JOB_OK",
            extra={"job_id": event.job_id, "run_time": str(event.scheduled_run_time)}
        )

def add_jobs():
    tz = pytz.timezone(TIMEZONE)
    trigger = CronTrigger(hour=DEFAULT_SEND_HOUR, minute=0, timezone=tz)
    scheduler.add_job(run_daily, trigger, id="daily_issue", replace_existing=True)
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    logger.info(f"Job registered: daily_issue at {DEFAULT_SEND_HOUR:02d}:00 {TIMEZONE}")

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

def shutdown_scheduler(wait: bool = False):
    if scheduler.running:
        scheduler.shutdown(wait=wait)
        logger.info("APScheduler stopped")
