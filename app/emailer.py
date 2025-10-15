# app/emailer.py
from typing import List, Dict, Iterable, Optional
import os
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

# ---- Config (pulled from your config module, but with safe fallbacks) ----
try:
    from .config import (
        EMAIL_FROM, EMAIL_TO,
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
        SENDGRID_API_KEY,
    )
except Exception:
    # If some are commented out in config.py, prevent import errors:
    EMAIL_FROM = os.getenv("EMAIL_FROM", "bot@example.com")
    EMAIL_TO = os.getenv("EMAIL_TO", "you@example.com")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

# Optional: choose how to send: console | sendgrid | smtp
SEND_MODE = os.getenv("SEND_MODE", ("sendgrid" if SENDGRID_API_KEY else "smtp" if SMTP_HOST else "console")).lower()
REQUESTS_TIMEOUT = float(os.getenv("REQUESTS_TIMEOUT", "15"))

HTML_TPL = Template("""
<h2>Quantum Daily — {{ date }}</h2>
{% for it in items %}
  <div style="margin:12px 0;padding:10px;border:1px solid #eee;border-radius:8px;">
    <div style="font-size:16px;font-weight:600;">{{ it.title }}</div>
    <div style="font-size:12px;color:#666;">{{ it.category }} • {{ it.source }} • {{ it.published_at }}</div>
    <p>{{ it.summary }}</p>
    <div style="font-size:12px;">
      <a href="{{ it.url }}">Read</a>
      <!-- Keep feedback instructions in the API/UI; emails are better with minimal code blocks -->
    </div>
  </div>
{% endfor %}
""")

def render_html(date: str, items: List[Dict]) -> str:
    return HTML_TPL.render(date=date, items=items)

def _render_text_fallback(date: str, items: List[Dict]) -> str:
    # Simple plaintext body for clients that prefer it
    lines = [f"Quantum Daily — {date}", ""]
    for it in items:
        lines += [
            f"- {it.get('title','(no title)')}",
            f"  {it.get('category','')} • {it.get('source','')} • {it.get('published_at','')}",
            f"  {it.get('summary','')}",
            f"  {it.get('url','')}",
            ""
        ]
    return "\n".join(lines).strip()

def send_email(
    subject: str,
    html: str,
    to: Optional[Iterable[str]] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """
    Returns True on success, False on failure.
    Honors SEND_MODE = console | sendgrid | smtp
    """
    recipients = list(to) if to is not None else [EMAIL_TO]
    if not recipients:
        print("[emailer] No recipients; aborting.")
        return False

    text = _render_text_fallback(_extract_date_from_subject(subject), [])  # if you pass items, render here
    # build multipart message for SMTP path
    msg = _build_multipart_message(subject, EMAIL_FROM, recipients, html, text, reply_to)

    try:
        if SEND_MODE == "console":
            _send_console(subject, recipients, html)
            return True
        elif SEND_MODE == "sendgrid":
            return _send_via_sendgrid(subject, html, recipients, reply_to)
        elif SEND_MODE == "smtp":
            return _send_via_smtp(msg, recipients)
        else:
            print(f"[emailer] Unknown SEND_MODE={SEND_MODE!r}; falling back to console.")
            _send_console(subject, recipients, html)
            return True
    except Exception as e:
        print(f"[emailer] ERROR during send ({SEND_MODE}): {e}")
        return False

def _build_multipart_message(subject, sender, recipients, html, text, reply_to) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg

def _send_console(subject: str, recipients: List[str], html: str) -> None:
    preview = html if len(html) < 1200 else html[:1200] + "…"
    print(f"[EMAIL console]\nTo: {', '.join(recipients)}\nSubject: {subject}\n---\n{preview}\n---\n")

def _send_via_sendgrid(subject: str, html: str, recipients: List[str], reply_to: Optional[str]) -> bool:
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY missing while SEND_MODE=sendgrid")
    import requests
    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": EMAIL_FROM},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=REQUESTS_TIMEOUT,
    )
    if r.status_code >= 300:
        # Surface useful diagnostics for debugging
        raise RuntimeError(f"SendGrid {r.status_code}: {r.text}")
    return True

def _send_via_smtp(msg: MIMEMultipart, recipients: List[str]) -> bool:
    if not SMTP_HOST:
        raise RuntimeError("SMTP_HOST missing while SEND_MODE=smtp")
    ctx = ssl.create_default_context()
    # Some providers require 465 (implicit TLS). If you use 465, use SMTP_SSL instead of SMTP+starttls.
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=REQUESTS_TIMEOUT) as server:
        server.ehlo()
        try:
            server.starttls(context=ctx)
            server.ehlo()
        except smtplib.SMTPException:
            # Server may already enforce TLS (or you're on port 25 locally) — proceed without starttls
            pass
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(msg["From"], recipients, msg.as_string())
    return True

def _extract_date_from_subject(subject: str) -> str:
    # best-effort; helps the text fallback if you want to include items there in the future
    # e.g., "Quantum Daily — 2025-10-15"
    import re
    m = re.search(r"\d{4}-\d{2}-\d{2}", subject)
    return m.group(0) if m else ""
