# app/routers/email_admin.py
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
import os
from app.emailer import send_email

router = APIRouter(prefix="/admin/email", tags=["Admin Email"])

# --- Simple API key gate (replace with real auth later if needed) ---
def require_admin(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected:
        # Fail closed if you forgot to set the key
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: ADMIN_API_KEY not set."
        )
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

@router.post("/send-test", summary="Send a test email to configured recipient")
def send_test_email(bg: BackgroundTasks, _: None = Depends(require_admin)):
    """
    Queues a simple test email using the currently configured email backend (SMTP or SendGrid).
    Returns immediately; check your inbox afterwards.
    """
    bg.add_task(send_email, "Quantum Daily — test", "<p>Hello! This is a test email.</p>")
    return {"queued": True}
