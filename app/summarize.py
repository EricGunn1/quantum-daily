# app/summarize.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
import os, json

import httpx
from openai import OpenAI

# Optional deps — gracefully degrade if missing
try:
    import trafilatura  # type: ignore
except Exception:
    trafilatura = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None  # type: ignore

# Logging (optional but recommended if you have this helper)
try:
    from app.logging_setup import get_logger
    logger = get_logger("quantum_daily.summarize")
except Exception:  # fallback
    import logging
    logger = logging.getLogger("quantum_daily.summarize")

# Prefer a preconfigured client from your config, else build from env
_client: Optional[OpenAI] = None
try:
    # If your app.config exports a ready OpenAI client named `client`, we’ll use it.
    from app.config import client as _preconfigured_client  # type: ignore
except Exception:
    _preconfigured_client = None  # type: ignore

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYS_PROMPT = (
    "You are a concise news summarizer. Output plain, non-jargon English. "
    "Avoid hype; stick to facts present in the text."
)

def _get_client() -> Optional[OpenAI]:
    global _client
    if _client is not None:
        return _client
    if _preconfigured_client is not None:
        _client = _preconfigured_client
        return _client
    if OPENAI_API_KEY:
        _client = OpenAI(api_key=OPENAI_API_KEY)
        return _client
    return None

def _truncate(s: str, max_chars: int = 9000) -> str:
    return s[:max_chars] if s else s

def _fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    headers = {"User-Agent": "QuantumDailyBot/1.0 (+https://example.com)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            return r.text
    except Exception as e:
        logger.warning("FETCH_HTML_FAILED", extra={"url": url, "error": type(e).__name__})
        return None

def _extract_text_and_title(html: str) -> Tuple[str, Optional[str]]:
    # 1) Try trafilatura
    if trafilatura:
        try:
            text = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
            title = None
            try:
                md = trafilatura.metadata.extract_metadata(html)
                if md and getattr(md, "title", None):
                    title = md.title  # type: ignore[attr-defined]
            except Exception:
                pass
            if text:
                return text, title
        except Exception as e:
            logger.debug("TRAFILATURA_EXTRACT_FAILED", extra={"error": type(e).__name__})

    # 2) Fallback: BeautifulSoup
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else None
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = " ".join(s for s in soup.stripped_strings)
            return text, title
        except Exception as e:
            logger.debug("BS4_EXTRACT_FAILED", extra={"error": type(e).__name__})

    # 3) Last resort: raw html
    return html, None

def _ensure_content(it: Dict) -> Dict:
    """
    If item has no 'content' but has 'url', fetch & extract text.
    Potentially updates 'title' with extracted title if missing.
    """
    text = it.get("content") or ""
    url = it.get("url") or ""
    if text or not url:
        return it

    html = _fetch_html(url)
    if not html:
        return it

    body, title_guess = _extract_text_and_title(html)
    if body:
        it["content"] = body
    if title_guess and not it.get("title"):
        it["title"] = title_guess
    return it

def _summarize_one(client: OpenAI, it: Dict) -> None:
    """
    Calls OpenAI to produce a JSON summary with keys:
      - plain_summary: str (80–120 words)
      - tldr_bullets: list[str] (<=3)
    Also sets legacy 'summary' for backward compatibility.
    """
    title = it.get("title") or ""
    url = it.get("url") or ""
    text = it.get("content") or ""
    if not text:
        logger.warning("NO_CONTENT_TO_SUMMARIZE", extra={"url": url})
        return

    user_prompt = f"""
Summarize the article in 80–120 words of plain, non-jargon English.
Then provide up to 3 TL;DR bullets. Avoid hype; stick to facts stated in the text.
If claims are speculative, add one caveat bullet.

Return strict JSON with keys:
  - plain_summary: string
  - tldr_bullets: array of up to 3 strings

TITLE: {title}
URL: {url}
ARTICLE:
{_truncate(text)}
""".strip()

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Respond with valid JSON only."},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content
        data = json.loads(content)

        plain = (data.get("plain_summary") or "").strip()
        bullets = data.get("tldr_bullets") or []

        # Backward compatibility: keep your original 'summary' field populated
        it["plain_summary"] = plain
        it["tldr_bullets"] = bullets
        it["summary"] = plain if plain else (it.get("summary") or "")

    except Exception as e:
        logger.exception("OPENAI_SUMMARY_FAILED", extra={"url": url, "error": type(e).__name__})
        # Minimal fallback: keep old behavior
        it["summary"] = (it.get("content") or it.get("title", ""))[:280]

def summarize_items(items: List[Dict]) -> List[Dict]:
    """
    Public API: enrich each item with (plain_summary, tldr_bullets, summary).
    - Ensures content by fetching the URL when missing.
    - Uses OpenAI if configured; otherwise simple local fallback.
    """
    client = _get_client()

    if not client:
        # Dev fallback without LLM
        for it in items:
            it = _ensure_content(it)
            text = it.get("content") or it.get("title", "")
            it["plain_summary"] = text[:280]
            it["tldr_bullets"] = []
            it["summary"] = it["plain_summary"]
        return items

    for it in items:
        _ensure_content(it)
        _summarize_one(client, it)

    return items
