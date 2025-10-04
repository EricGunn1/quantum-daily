from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import select
from datetime import datetime

from ..logging_setup import get_logger
from ..store import get_session
from ..models import DailyIssue
from ..workflow import run_daily
from ..render_issue import render_issue_html
from ..summarize import summarize_items

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

@router.get("/today.html", response_class=HTMLResponse)
def get_today_html(regen: bool = Query(False)):
    """
    Render today's issue as HTML.
    - Generates today's issue if missing or when ?regen=1
    - If stored items lack summaries, summarizes them on the fly
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        issue_json = run_daily() if (regen or not issue) else issue.items_json

        items = issue_json.get("items", [])
        if any(not (it.get("plain_summary") or it.get("summary")) for it in items):
            logger.info("Summarizing items missing summaries (HTML path)", extra={"missing": True})
            issue_json["items"] = summarize_items(items)

            # (Optional) persist enriched summaries back to DB so future loads are ready-made:
            # s.add(DailyIssue(date=today, items_json=issue_json))
            # s.commit()

    return HTMLResponse(render_issue_html(issue_json))