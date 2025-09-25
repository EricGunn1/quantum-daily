# app/middleware.py
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .logging_setup import request_id_var, get_logger

logger = get_logger("quantum_daily.http")

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(req_id)
        logger.info(f"REQUEST START: {request.method} {request.url.path}")
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = getattr(response, "status_code", "NA")
            logger.info(f"REQUEST END: {request.method} {request.url.path} -> {status} ({elapsed_ms:.1f} ms)")
            request_id_var.reset(token)
