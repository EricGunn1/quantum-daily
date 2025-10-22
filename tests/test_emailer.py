# tests/test_emailer.py
import os
from app.emailer import send_email

def test_send_email_console(monkeypatch):
    monkeypatch.setenv("SEND_MODE", "console")
    assert send_email("Test", "<p>hi</p>") is True
