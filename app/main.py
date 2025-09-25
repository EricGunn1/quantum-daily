from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select
from .store import init_db, get_session
from .models import DailyIssue, Feedback, UserPrefs
from .schema import FeedbackIn, PrefsIn
from .ranker import apply_feedback
from apscheduler.schedulers.background import BackgroundScheduler
from .scheduler import start_scheduler
from .workflow import run_daily
from app.config import client
from pathlib import Path

app = FastAPI(title="Quantum Daily", version="0.1.0")

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = Path("static/favicon.ico")
    return FileResponse(path) if path.exists() else {}

@app.on_event("startup")
def _startup():
    init_db()
    if not getattr(app.state, "scheduler_started", False):
        start_scheduler()
        app.state.scheduler_started = True

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/summary/today")
def get_today():
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date==today)).first()
        if not issue:
            # generate on demand if missing
            issue_json = run_daily()
            return JSONResponse(issue_json)
        return JSONResponse(issue.items_json)

@app.post("/run-once")
def run_once():
    return JSONResponse(run_daily())

@app.post("/feedback")
def post_feedback(body: FeedbackIn):
    with get_session() as s:
        s.add(Feedback(article_id=body.article_id, signal=body.signal, aspect=body.aspect))
        s.commit()
        # apply immediately to prefs
        prefs = s.exec(select(UserPrefs)).first()
        prefs = apply_feedback(prefs, [body])
        s.add(prefs); s.commit()
    return {"ok": True}

@app.post("/prefs")
def update_prefs(body: PrefsIn):
    with get_session() as s:
        prefs = s.exec(select(UserPrefs)).first()
        if not prefs:
            prefs = UserPrefs()
        if body.industry_weight is not None and body.tech_weight is not None:
            total = max(1e-6, body.industry_weight + body.tech_weight)
            prefs.industry_weight = body.industry_weight/total
            prefs.tech_weight = body.tech_weight/total
        if body.email is not None:
            prefs.email = body.email
        if body.send_hour_local is not None:
            prefs.send_hour_local = int(body.send_hour_local)
        s.add(prefs); s.commit()
    return {"ok": True}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to Quantum Daily API"}