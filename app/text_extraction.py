# app/text_extraction.py
from __future__ import annotations
from typing import Tuple, Optional
import httpx

def fetch_and_extract(url: str, timeout: int = 15) -> Tuple[str, Optional[str]]:
    """
    Fetches URL and returns (main_text, title_guess). Uses trafilatura if available,
    falls back to BeautifulSoup, and finally raw text if all else fails.
    """
    headers = {"User-Agent": "QuantumDailyBot/1.0 (+https://example.com)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            html = r.text
    except Exception:
        return "", None

    # Best: trafilatura
    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
        title = None
        try:
            md = trafilatura.metadata.extract_metadata(html)
            if md and md.title:
                title = md.title
        except Exception:
            pass
        if text:
            return text, title
    except Exception:
        pass

    # Fallback: BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(s for s in soup.stripped_strings)
        return text, title
    except Exception:
        pass

    # Last resort
    return html, None
