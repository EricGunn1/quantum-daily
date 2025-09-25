# app/main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select
from pathlib import Path

from .logging_setup import setup_logging, get_logger
from .middleware import RequestContextMiddleware
from .store import init_db, get_session
from .models import DailyIssue, Feedback, UserPrefs
from .schema import FeedbackIn, PrefsIn
from .ranker import apply_feedback
from .scheduler import add_jobs, start_scheduler, shutdown_scheduler
from .workflow import run_daily

setup_logging()  # <-- set up logging ASAP
logger = get_logger("quantum_daily.main")

app = FastAPI(title="Quantum Daily", version="0.1.0")
app.add_middleware(RequestContextMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = Path("static/favicon.ico")
    return FileResponse(path) if path.exists() else {}

# ---- Exception Handlers ----
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # "Handled" because we're catching and turning into a response on purpose
    logger.exception("HTTP_EXCEPTION", extra={"handled": True, "path": str(request.url.path), "status_code": exc.status_code})
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # "Unhandled" because we didn't expect this. We still log full traceback.
    logger.exception("UNHANDLED_EXCEPTION", extra={"handled": False, "path": str(request.url.path)})
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

# ---- Lifespan ----
@app.on_event("startup")
def _startup():
    logger.info("APP STARTUP")
    init_db()
    if not getattr(app.state, "scheduler_started", False):
        logger.info("Registering scheduler jobs")
        add_jobs()
        start_scheduler()
        app.state.scheduler_started = True
        logger.info("Scheduler started")

@app.on_event("shutdown")
def _shutdown():
    logger.info("APP SHUTDOWN")
    if getattr(app.state, "scheduler_started", False):
        logger.info("Stopping scheduler")
        shutdown_scheduler(wait=False)
        app.state.scheduler_started = False

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
