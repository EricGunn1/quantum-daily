import os
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
EMAIL_TO = os.getenv("EMAIL_TO", "eng0130@gmail.com")
# EMAIL_FROM = os.getenv("EMAIL_FROM", "bot@example.com")
# SMTP_HOST = os.getenv("SMTP_HOST", "")
# SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
# SMTP_USER = os.getenv("SMTP_USER", "")
# SMTP_PASS = os.getenv("SMTP_PASS", "")
# SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")  # optional
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
DEFAULT_SEND_HOUR = int(os.getenv("DEFAULT_SEND_HOUR", "8"))
# DB_URL = os.getenv("DB_URL", "sqlite:///quantum_daily.db")
