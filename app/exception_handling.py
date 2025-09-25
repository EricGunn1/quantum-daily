# app/exception_handling.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .logging_setup import get_logger

# Keep a separate logger namespace for exceptions
logger = get_logger("quantum_daily.exceptions")


async def http_exception_handler(request: Request, exc: HTTPException):
    # Mirrors your existing behavior: log as "handled" with status code
    logger.exception(
        "HTTP_EXCEPTION",
        extra={"handled": True, "path": str(request.url.path), "status_code": exc.status_code},
    )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception):
    # Mirrors your existing behavior: log full traceback as "unhandled"
    logger.exception(
        "UNHANDLED_EXCEPTION",
        extra={"handled": False, "path": str(request.url.path)},
    )
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers in one place.
    Call from app/main.py after creating the FastAPI app.
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
