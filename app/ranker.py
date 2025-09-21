from datetime import datetime, timezone

def naive_score(item):
    # simple recency score: newer = higher
    now = datetime.now(timezone.utc)
    dt = item["published_at"] or now
    age_hours = max(1.0, (now - dt).total_seconds() / 3600)
    return 1.0 / age_hours
