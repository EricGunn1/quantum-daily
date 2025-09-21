# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .store import init_db
# If you haven't wired the scheduler yet, you can omit these:
# from .scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- STARTUP SECTION ----
    # Create any missing tables before serving requests
    init_db()

    # Start background jobs (optional)
    # try:
        # start_scheduler()  # guarded to avoid starting twice
    # except Exception as e:
        # Don’t crash the app if the scheduler fails; log and continue
        # print(f"[lifespan] scheduler start failed: {e}")

    # Hand control back to FastAPI to serve requests
    yield

    # ---- SHUTDOWN SECTION ----
    # Stop background jobs (optional)
    # try:
    #     stop_scheduler()
    # except Exception as e:
    #     print(f"[lifespan] scheduler stop failed: {e}")

# Pass the lifespan handler to the app
app = FastAPI(
    title="Quantum Daily",
    version="0.0.3",
    lifespan=lifespan,
)

# --- routes as usual ---
@app.get("/health")
def health():
    return {"status": "ok"}
