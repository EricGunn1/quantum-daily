# app/workflow.py
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import select

from .sources import fetch_all
from .ranker import classify_industry_vs_tech, composite_score
from .summarize import summarize_items
from .models import Article, DailyIssue, UserPrefs
from .store import get_session
from .emailer import render_html, send_email
from .logging_setup import get_logger

logger = get_logger("quantum_daily.workflow")

TOP_N = 12  # number of items to include in the daily issue


def run_daily() -> Dict[str, Any]:
    """
    Orchestrates the daily run:
    - load/create user prefs
    - fetch sources
    - classify, score, rank
    - summarize
    - persist articles + issue
    - email HTML
    """
    logger.info("RUN_DAILY_START")

    # Outer catch: any unexpected failure is logged with handled=False and re-raised.
    try:
        with get_session() as s:
            # --- Prefs ---
            prefs = s.exec(select(UserPrefs)).first()
            if not prefs:
                prefs = UserPrefs(email="", send_hour_local=8)
                s.add(prefs)
                s.commit()
                s.refresh(prefs)
                logger.info("Created default UserPrefs", extra={"handled": True})

            # --- Fetch ---
            try:
                raw: List[Dict[str, Any]] = fetch_all()
                logger.info("FETCH_OK", extra={"count": len(raw)})
            except Exception:
                logger.exception("FETCH_FAILED", extra={"handled": True})
                raw = []

            # --- Classify & Score ---
            scored: List[Dict[str, Any]] = []
            for it in raw:
                url = it.get("url", "")
                try:
                    cls = classify_industry_vs_tech(it)
                except Exception:
                    logger.exception(
                        "CLASSIFY_FAILED",
                        extra={"handled": True, "url": url},
                    )
                    cls = {"industry": 0.0, "tech": 0.0}

                try:
                    score = float(composite_score(it, cls, prefs))
                except Exception:
                    logger.exception(
                        "SCORE_FAILED",
                        extra={"handled": True, "url": url},
                    )
                    score = 0.0

                it["category"] = "industry" if cls.get("industry", 0) >= cls.get("tech", 0) else "tech"
                it["score"] = score
                scored.append(it)

            logger.info("SCORING_DONE", extra={"count": len(scored)})

            # --- Select Top N ---
            top = sorted(scored, key=lambda x: x.get("score", 0.0), reverse=True)[:TOP_N]
            logger.info("RANKING_DONE", extra={"selected": len(top), "top_n": TOP_N})

            # --- Summarize ---
            try:
                top = summarize_items(top)
                logger.info("SUMMARY_OK", extra={"count": len(top)})
            except Exception:
                logger.exception("SUMMARY_FAILED", extra={"handled": True})
                # proceed without summaries if summarization fails

            # --- Persist Articles ---
            persisted_ids: List[int] = []
            for it in top:
                try:
                    a = Article(
                        url=it.get("url", ""),
                        title=it.get("title", ""),
                        content=it.get("content", ""),
                        published_at=it.get("published_at"),
                        source=it.get("source", ""),
                        topics=[it.get("category", "")],
                    )
                    s.add(a)
                    s.commit()
                    s.refresh(a)
                    it["id"] = a.id
                    persisted_ids.append(a.id)
                except Exception:
                    logger.exception(
                        "PERSIST_ARTICLE_FAILED",
                        extra={"handled": True, "url": it.get("url", "")},
                    )

            logger.info("ARTICLES_PERSISTED", extra={"count": len(persisted_ids)})

            # --- Persist Issue ---
            date = datetime.utcnow().strftime("%Y-%m-%d")
            issue_items = [{k: v for k, v in it.items() if k != "content"} for it in top]
            issue_json: Dict[str, Any] = {"date": date, "items": issue_items}

            try:
                s.add(DailyIssue(date=date, items_json=issue_json))
                s.commit()
                logger.info("ISSUE_PERSISTED", extra={"date": date, "items": len(issue_items)})
            except Exception:
                logger.exception("PERSIST_ISSUE_FAILED", extra={"handled": True, "date": date})

            # --- Render Email ---
            html = None
            try:
                html = render_html(date, issue_items)
                logger.debug("EMAIL_RENDER_OK", extra={"length": len(html) if html else 0})
            except Exception:
                logger.exception("EMAIL_RENDER_FAILED", extra={"handled": True, "date": date})

            # --- Send Email ---
            if html:
                try:
                    send_email(f"Quantum Daily — {date}", html)
                    logger.info("EMAIL_SENT", extra={"handled": True, "prefs_email": (prefs.email or "").strip()})
                except Exception:
                    logger.exception("EMAIL_FAILED", extra={"handled": True, "prefs_email": (prefs.email or "").strip()})
            else:
                logger.info("EMAIL_SKIPPED", extra={"handled": True, "reason": "no_html"})

            logger.info("RUN_DAILY_SUCCESS", extra={"handled": True})
            return issue_json

    except Exception:
        logger.exception("RUN_DAILY_FATAL", extra={"handled": False})
        raise
