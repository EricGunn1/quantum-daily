# app/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .logging_setup import setup_logging, get_logger
from .middleware import RequestContextMiddleware
from .store import get_session
from .models import DailyIssue, Feedback, UserPrefs
from .schema import FeedbackIn, PrefsIn
from .ranker import apply_feedback
from .workflow import run_daily
from .exception_handling import register_exception_handlers
from .lifespan import lifespan

from .routers import health, summary, feedback, prefs
from .routers.email_admin import router as email_admin_router

# app/main.py
import sys, asyncio  # add these
# Use the Proactor policy on Windows (supports subprocesses required by Playwright)
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


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

@app.get("/", include_in_schema=False)
def root():
    # Use 307 so GET stays a GET
    return RedirectResponse(url="/summary/today.html", status_code=307)

# Include routers
app.include_router(health.router)
app.include_router(summary.router)
app.include_router(feedback.router)
app.include_router(prefs.router)
app.include_router(email_admin_router)