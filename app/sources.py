import feedparser
from datetime import datetime, timezone
from typing import List, Dict

QUANTUM_FEEDS = [
    # General/industry-oriented
    "https://news.google.com/rss/search?q=quantum+computing+industry",
    "https://www.prnewswire.com/rss/technology-latest-news.rss",
    "https://www.hpcwire.com/feed/",
    # Company/press
    "https://www.ibm.com/blogs/research/category/quantum/feed/",
    "https://www.quantinuum.com/rss.xml",
    "https://ionq.com/rss.xml",
    # Research (lower priority by default)
    "https://export.arxiv.org/rss/quant-ph"
]

def fetch_all() -> List[Dict]:
    items = []
    for url in QUANTUM_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                items.append({
                    "url": getattr(e, "link", ""),
                    "title": getattr(e, "title", ""),
                    "content": getattr(e, "summary", ""),
                    "published_at": _parse(getattr(e, "published", "")),
                    "source": feed.feed.get("title", url)
                })
        except Exception:
            continue
    return items

def _parse(published: str):
    try:
        dt = datetime(*feedparser._parse_date(published)[:6], tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
