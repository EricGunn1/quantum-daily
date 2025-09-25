from datetime import datetime
from sqlmodel import select
from .sources import fetch_all
from .ranker import classify_industry_vs_tech, composite_score
from .summarize import summarize_items
from .models import Article, DailyIssue, UserPrefs
from .store import get_session
from .emailer import render_html, send_email

def run_daily():
    with get_session() as s:
        prefs = s.exec(select(UserPrefs)).first()
        if not prefs:
            prefs = UserPrefs(email="", send_hour_local=8)
            s.add(prefs); s.commit(); s.refresh(prefs)

        raw = fetch_all()
        # classify & score
        scored = []
        for it in raw:
            cls = classify_industry_vs_tech(it)
            score = composite_score(it, cls, prefs)
            it["category"] = "industry" if cls["industry"] >= cls["tech"] else "tech"
            it["score"] = score
            scored.append(it)
        # take top N
        top = sorted(scored, key=lambda x: x["score"], reverse=True)[:12]
        top = summarize_items(top)

        # persist articles and issue
        article_rows = []
        for it in top:
            a = Article(url=it["url"], title=it["title"], content=it.get("content",""),
                        published_at=it.get("published_at"), source=it.get("source",""),
                        topics=[it["category"]])
            s.add(a); s.commit(); s.refresh(a)
            it["id"] = a.id
            article_rows.append(a)

        date = datetime.utcnow().strftime("%Y-%m-%d")
        issue_json = {"date": date, "items": [{k:v for k,v in it.items() if k != "content"} for it in top]}
        s.add(DailyIssue(date=date, items_json=issue_json))
        s.commit()

        html = render_html(date, issue_json["items"])
        send_email(f"Quantum Daily — {date}", html)
        return issue_json
