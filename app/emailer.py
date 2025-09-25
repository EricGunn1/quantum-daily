from typing import List, Dict
from jinja2 import Template
import smtplib, ssl
from email.mime.text import MIMEText
from .config import EMAIL_FROM, EMAIL_TO, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SENDGRID_API_KEY

HTML_TPL = Template("""
<h2>Quantum Daily — {{ date }}</h2>
{% for it in items %}
  <div style="margin:12px 0;padding:10px;border:1px solid #eee;border-radius:8px;">
    <div style="font-size:16px;font-weight:600;">{{ it.title }}</div>
    <div style="font-size:12px;color:#666;">{{ it.category }} • {{ it.source }} • {{ it.published_at }}</div>
    <p>{{ it.summary }}</p>
    <div style="font-size:12px;">
      <a href="{{ it.url }}">Read</a> |
      Feedback: 
      <code>POST /feedback {"article_id": {{ it.id }}, "signal": "+1"|"-1"|"more"|"less", "aspect":"industry|tech|source:NAME|topic:TAG"}</code>
    </div>
  </div>
{% endfor %}
""")

def render_html(date: str, items: List[Dict]) -> str:
    return HTML_TPL.render(date=date, items=items)

def send_email(subject: str, html: str):
    if SENDGRID_API_KEY:
        import requests, json
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}",
                     "Content-Type":"application/json"},
            json={
              "personalizations":[{"to":[{"email": EMAIL_TO}]}],
              "from":{"email": EMAIL_FROM},
              "subject": subject,
              "content":[{"type":"text/html","value": html}]
            }
        )
        return
    # SMTP fallback
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
