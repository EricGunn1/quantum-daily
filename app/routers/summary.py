from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlmodel import select
from datetime import datetime

from ..logging_setup import get_logger
from ..store import get_session
from ..models import DailyIssue
from ..workflow import run_daily

logger = get_logger("quantum_daily.routes.summary")

router = APIRouter(prefix="/summary")

@router.get("/today")
def get_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"Fetching daily issue for {today}")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        if not issue:
            logger.info("No stored issue; generating on-demand")
            return JSONResponse(run_daily())
        return JSONResponse(issue.items_json)

@router.post("/run-once", include_in_schema=False)
def run_once():
    logger.info("Manual run_once invoked")
    return JSONResponse(run_daily())
