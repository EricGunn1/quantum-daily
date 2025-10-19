import os
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI

# Go up one level from app/ to root/
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")

# Create reusable OpenAI client
client = OpenAI(api_key=api_key)


# Other configuration variables
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
# SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")  # optional
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
DEFAULT_SEND_HOUR = int(os.getenv("DEFAULT_SEND_HOUR", "8"))
DB_URL = os.getenv("DB_URL", "sqlite:///quantum_daily.db")
