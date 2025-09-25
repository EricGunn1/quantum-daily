# app/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select
from pathlib import Path

from .logging_setup import setup_logging, get_logger
from .middleware import RequestContextMiddleware
from .store import get_session
from .models import DailyIssue, Feedback, UserPrefs
from .schema import FeedbackIn, PrefsIn
from .ranker import apply_feedback
from .workflow import run_daily
from .exception_handling import register_exception_handlers
from .lifespan import lifespan   # <-- NEW

setup_logging()  # <-- set up logging ASAP
logger = get_logger("quantum_daily.main")

app = FastAPI(title="Quantum Daily", version="0.1.0", lifespan=lifespan)  # <-- pass lifespan
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = Path("static/favicon.ico")
    return FileResponse(path) if path.exists() else {}

# ---- Routes ----
@app.get("/health")
def health():
    logger.debug("Health check invoked")
    return {"status": "ok"}

@app.get("/summary/today")
def get_today():
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"Fetching daily issue for {today}")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        if not issue:
            logger.info("No stored issue; generating on-demand")
            issue_json = run_daily()  # run_daily will log its own steps/exceptions
            return JSONResponse(issue_json)
        return JSONResponse(issue.items_json)

@app.post("/run-once")
def run_once():
    logger.info("Manual run_once invoked")
    return JSONResponse(run_daily())

@app.post("/feedback")
def post_feedback(body: FeedbackIn):
    logger.info(f"Feedback received: article={body.article_id} signal={body.signal} aspect={body.aspect}")
    with get_session() as s:
        s.add(Feedback(article_id=body.article_id, signal=body.signal, aspect=body.aspect))
        s.commit()
        prefs = s.exec(select(UserPrefs)).first()
        prefs = apply_feedback(prefs, [body])
        s.add(prefs); s.commit()
    return {"ok": True}

@app.post("/prefs")
def update_prefs(body: PrefsIn):
    logger.info("Updating preferences")
    with get_session() as s:
        prefs = s.exec(select(UserPrefs)).first() or UserPrefs()
        if body.industry_weight is not None and body.tech_weight is not None:
            total = max(1e-6, body.industry_weight + body.tech_weight)
            prefs.industry_weight = body.industry_weight / total
            prefs.tech_weight = body.tech_weight / total
        if body.email is not None:
            prefs.email = body.email
        if body.send_hour_local is not None:
            prefs.send_hour_local = int(body.send_hour_local)
        s.add(prefs); s.commit()
    return {"ok": True}

@app.get("/")
def read_root():
    logger.debug("Root hit")
    return {"status": "ok", "message": "Welcome to Quantum Daily API"}
