from fastapi import APIRouter
from ..logging_setup import get_logger

logger = get_logger("quantum_daily.routes.health")

router = APIRouter()

@router.get("/health")
def health():
    logger.debug("Health check invoked")
    return {"status": "ok"}

@router.get("/")
def read_root():
    logger.debug("Root hit")
    return {"status": "ok", "message": "Welcome to Quantum Daily API"}
