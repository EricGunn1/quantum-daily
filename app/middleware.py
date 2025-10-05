# app/middleware.py
import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging_setup import request_id_var, get_logger

logger = get_logger("quantum_daily.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate a request id and store it in a ContextVar (your logger can pull this in formatters)
        req_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(req_id)

        start = time.perf_counter()
        response: Optional[Response] = None

        try:
            logger.info(f"REQUEST START: {request.method} {request.url.path}")
            response = await call_next(request)
            return response
        except Exception:
            # Log the exception and re-raise so your global exception handlers can respond
            logger.exception(f"REQUEST EXCEPTION: {request.method} {request.url.path}")
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = getattr(response, "status_code", 500)  # default to 500 if response never got set
            logger.info(f"REQUEST END: {request.method} {request.url.path} -> {status} ({elapsed_ms:.1f} ms)")
            # Restore previous request id context
            request_id_var.reset(token)
