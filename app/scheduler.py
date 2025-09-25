from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
from .config import TIMEZONE, DEFAULT_SEND_HOUR
from .workflow import run_daily

scheduler = BackgroundScheduler()

def start_scheduler():
    tz = pytz.timezone(TIMEZONE)
    trigger = CronTrigger(hour=DEFAULT_SEND_HOUR, minute=0, timezone=tz)
    scheduler.add_job(run_daily, trigger, id="daily_issue", replace_existing=True)
    scheduler.start()
