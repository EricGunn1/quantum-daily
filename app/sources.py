# app/sources.py
"""
Search-based news sources for 'quantum computing' (or any topic).
Providers:
  - GoogleNewsRSSProvider: query-driven RSS, no API key
  - NewsAPIProvider: optional, requires NEWSAPI_KEY
  - StaticRSSProvider: your old fixed RSS list (optional fallback)

Call fetch_all(topic="quantum computing", since_hours=24) each day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
import os
import time
import hashlib
import requests
import feedparser

# ---------- Utilities ----------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _coerce_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _parse_feed_datetime(published: str) -> Optional[datetime]:
    """Best-effort parser for feedparser 'published'."""
    try:
        # feedparser has a helper: _parse_date; returns a time tuple
        tt = feedparser._parse_date(published)
        if not tt:
            return None
        return datetime(*tt[:6], tzinfo=timezone.utc)
    except Exception:
        return None

def _dedupe(items: List[Dict]) -> List[Dict]:
    """Deduplicate by normalized URL or title hash."""
    seen: set[str] = set()
    out: List[Dict] = []
    for it in items:
        key_raw = (it.get("url") or "").strip().lower() or (it.get("title") or "").strip().lower()
        key = hashlib.sha1(key_raw.encode("utf-8", errors="ignore")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

# ---------- Provider base ----------

@dataclass
class ProviderResult:
    items: List[Dict]
    source_name: str

class BaseProvider:
    name = "base"

    def fetch(self, topic: str, since: datetime, max_items: int = 50) -> ProviderResult:
        raise NotImplementedError

# ---------- Google News RSS (query-based) ----------

class GoogleNewsRSSProvider(BaseProvider):
    """
    Uses Google News RSS to run a query, optionally constrained by recency.
    Pros: free, no key. Cons: RSS snippets can be short; publication time can vary.
    """

    name = "google_news_rss"

    def __init__(self, lang: str = "en", country: str = "US"):
        # Google News RSS accepts hl, gl, ceid
        self.lang = lang
        self.country = country
        self.ceid = f"{country}:{lang}"

    def _build_url(self, topic: str) -> str:
        # You can tune the query. `when:1d` is often honored by Google News.
        # Spaces -> '+', keep it simple.
        q = topic.replace(" ", "+")
        return (
            "https://news.google.com/rss/search?"
            f"q={q}+when:1d&hl={self.lang}&gl={self.country}&ceid={self.ceid}"
        )

    def fetch(self, topic: str, since: datetime, max_items: int = 50) -> ProviderResult:
        url = self._build_url(topic)
        feed = feedparser.parse(url)
        items: List[Dict] = []
        for e in feed.entries[: max_items * 2]:  # oversample then dedupe/filter
            published = _parse_feed_datetime(getattr(e, "published", ""))
            if published and published < since:
                continue
            items.append({
                "url": getattr(e, "link", ""),
                "title": getattr(e, "title", ""),
                "content": getattr(e, "summary", ""),
                "published_at": published,
                "source": feed.feed.get("title", "Google News"),
            })
        return ProviderResult(items=_dedupe(items)[:max_items], source_name=self.name)

# ---------- NewsAPI (optional) ----------

class NewsAPIProvider(BaseProvider):
    """
    https://newsapi.org/ — /everything endpoint
    Note: free key is for dev/testing; check TOS for production.
    """

    name = "newsapi"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch(self, topic: str, since: datetime, max_items: int = 50) -> ProviderResult:
        url = "https://newsapi.org/v2/everything"
        # NewsAPI expects ISO 8601 timestamps
        params = {
            "q": topic,
            "from": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": min(max_items, 100),
        }
        headers = {"X-Api-Key": self.api_key}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        items: List[Dict] = []
        for a in data.get("articles", []):
            # Parse publishedAt
            pub = a.get("publishedAt")  # e.g., "2025-10-15T12:34:56Z"
            try:
                published = datetime.strptime(pub, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if pub else None
            except Exception:
                published = None
            items.append({
                "url": a.get("url", ""),
                "title": a.get("title", ""),
                "content": a.get("description", "") or "",
                "published_at": published,
                "source": (a.get("source") or {}).get("name") or "NewsAPI",
            })
        return ProviderResult(items=_dedupe(items)[:max_items], source_name=self.name)

# ---------- Static fallback (optional) ----------

DEFAULT_RSS: List[str] = [
    "https://news.google.com/rss/search?q=quantum+computing+industry",
    "https://www.prnewswire.com/rss/technology-latest-news.rss",
    "https://www.hpcwire.com/feed/",
    "https://www.ibm.com/blogs/research/category/quantum/feed/",
    "https://www.quantinuum.com/rss.xml",
    "https://ionq.com/rss.xml",
    "https://export.arxiv.org/rss/quant-ph",
]

class StaticRSSProvider(BaseProvider):
    name = "static_rss"

    def __init__(self, feeds: Optional[List[str]] = None):
        self.feeds = feeds or DEFAULT_RSS

    def fetch(self, topic: str, since: datetime, max_items: int = 50) -> ProviderResult:
        items: List[Dict] = []
        for url in self.feeds:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries:
                    published = _parse_feed_datetime(getattr(e, "published", ""))
                    if published and published < since:
                        continue
                    items.append({
                        "url": getattr(e, "link", ""),
                        "title": getattr(e, "title", ""),
                        "content": getattr(e, "summary", ""),
                        "published_at": published,
                        "source": feed.feed.get("title", url),
                    })
            except Exception:
                continue
        return ProviderResult(items=_dedupe(items)[:max_items], source_name=self.name)

# ---------- Orchestrator ----------

def fetch_all(
    topic: str = "quantum computing",
    since_hours: int = 24,
    max_items_per_provider: int = 50,
    use_static_fallback: bool = True,
) -> List[Dict]:
    """
    Fetch recent items for a topic from multiple providers.
    - topic: search query (used by Google News RSS and NewsAPI)
    - since_hours: time window (e.g., last 24h)
    - max_items_per_provider: per provider limit before dedupe/merge
    - use_static_fallback: include your legacy fixed RSS list
    """
    since = _utc_now() - timedelta(hours=since_hours)

    providers: List[BaseProvider] = [GoogleNewsRSSProvider()]
    newsapi_key = os.getenv("NEWSAPI_KEY", "")
    if newsapi_key:
        providers.append(NewsAPIProvider(newsapi_key))
    if use_static_fallback:
        providers.append(StaticRSSProvider())

    all_items: List[Dict] = []
    for p in providers:
        try:
            res = p.fetch(topic=topic, since=since, max_items=max_items_per_provider)
            all_items.extend(res.items)
        except Exception as e:
            # soft-fail one provider; continue others
            # you can hook your logger here if desired
            print(f"[sources] provider={p.name} error={type(e).__name__}: {e}")
            continue

        # polite pacing if providers rate-limit
        time.sleep(0.3)

    # final dedupe + sort by published_at desc (fallback score)
    merged = _dedupe(all_items)
    merged.sort(key=lambda x: x.get("published_at") or datetime(1970,1,1, tzinfo=timezone.utc), reverse=True)
    return merged
