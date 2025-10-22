# tests/test_sources.py
import feedparser
from app.sources import fetch_all

def test_fetch_all_shape(mocker):
    # mock Google News RSS provider parse()
    fake = type("F", (), {})()
    fake.feed = {"title": "Google News"}
    fake.entries = [
        type("E", (), {"link": "http://a", "title": "A", "summary": "sum", "published": "Wed, 01 Jan 2025 12:00:00 GMT"}),
        type("E", (), {"link": "http://b", "title": "B", "summary": "sum", "published": "Wed, 01 Jan 2025 13:00:00 GMT"}),
    ]
    mocker.patch.object(feedparser, "parse", return_value=fake)

    items = fetch_all(topic="quantum computing", since_hours=720, max_items_per_provider=5, use_static_fallback=False)
    assert isinstance(items, list)
    assert len(items) >= 2
    it = items[0]
    for k in ["url", "title", "content", "published_at", "source"]:
        assert k in it
