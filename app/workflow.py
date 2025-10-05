# app/workflow.py
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path
import uuid
import time
from collections import Counter

from sqlmodel import select

from .sources import fetch_all
from .ranker import classify_industry_vs_tech, composite_score
from .summarize import summarize_items
from .models import Article, DailyIssue, UserPrefs
from .store import get_session
from .logging_setup import get_logger
from .render_issue import render_issue_pdf

logger = get_logger("quantum_daily.workflow")

TOP_N = 12  # number of items to include in the daily issue
PDF_OUTPUT_PATH = Path("exports/QuantumDaily.pdf")  # overwritten on every run


def run_daily() -> Dict[str, Any]:
    """
    Orchestrates the daily run:
    - load/create user prefs
    - fetch sources
    - classify, score, rank
    - summarize
    - persist articles + issue
    - generate and save PDF locally (overwrites)
    """
    run_id = uuid.uuid4().hex[:8]
    date = datetime.utcnow().strftime("%Y-%m-%d")

    def X(**fields):
        # Helper to attach correlation + common fields
        return {"run_id": run_id, "date": date, **fields}

    logger.info("RUN_DAILY_START", extra=X(step="start"))

    t0 = time.perf_counter()

    # Outer catch: any unexpected failure is logged with handled=False and re-raised.
    try:
        with get_session() as s:
            # --- Prefs ---
            t_prefs = time.perf_counter()
            prefs = s.exec(select(UserPrefs)).first()
            if not prefs:
                prefs = UserPrefs(email="", send_hour_local=8)
                s.add(prefs)
                s.commit()
                s.refresh(prefs)
                logger.info("PREFS_CREATED_DEFAULT", extra=X(step="prefs", handled=True))
            logger.info(
                "PREFS_READY",
                extra=X(
                    step="prefs",
                    elapsed_ms=round((time.perf_counter() - t_prefs) * 1000),
                    email=(prefs.email or "").strip(),
                    send_hour_local=prefs.send_hour_local,
                ),
            )

            # --- Fetch ---
            t_fetch = time.perf_counter()
            try:
                raw: List[Dict[str, Any]] = fetch_all()
                per_source = Counter([it.get("source", "unknown") for it in raw])
                logger.info(
                    "FETCH_OK",
                    extra=X(
                        step="fetch",
                        count=len(raw),
                        per_source=dict(per_source),
                        elapsed_ms=round((time.perf_counter() - t_fetch) * 1000),
                    ),
                )
                if logger.isEnabledFor(10):  # DEBUG
                    sample = [{"title": (it.get("title") or "")[:120], "url": it.get("url", "")} for it in raw[:5]]
                    logger.debug("FETCH_SAMPLE", extra=X(step="fetch", sample=sample))
            except Exception as e:
                logger.exception("FETCH_FAILED", extra=X(step="fetch", handled=True, error=type(e).__name__))
                raw = []

            # --- Classify & Score ---
            t_score = time.perf_counter()
            scored: List[Dict[str, Any]] = []
            classify_errors = 0
            score_errors = 0
            for it in raw:
                url = it.get("url", "")
                # classify
                try:
                    cls = classify_industry_vs_tech(it)
                except Exception as e:
                    classify_errors += 1
                    logger.exception(
                        "CLASSIFY_FAILED",
                        extra=X(step="classify", handled=True, url=url, error=type(e).__name__),
                    )
                    cls = {"industry": 0.0, "tech": 0.0}

                # score
                try:
                    score = float(composite_score(it, cls, prefs))
                except Exception as e:
                    score_errors += 1
                    logger.exception(
                        "SCORE_FAILED",
                        extra=X(step="score", handled=True, url=url, error=type(e).__name__),
                    )
                    score = 0.0

                it["category"] = "industry" if cls.get("industry", 0) >= cls.get("tech", 0) else "tech"
                it["score"] = score
                scored.append(it)

            cat_dist = Counter([it.get("category", "unknown") for it in scored])
            logger.info(
                "SCORING_DONE",
                extra=X(
                    step="score",
                    count=len(scored),
                    category_dist=dict(cat_dist),
                    classify_errors=classify_errors,
                    score_errors=score_errors,
                    elapsed_ms=round((time.perf_counter() - t_score) * 1000),
                ),
            )

            # --- Select Top N ---
            t_rank = time.perf_counter()
            top = sorted(scored, key=lambda x: x.get("score", 0.0), reverse=True)[:TOP_N]
            top_scores = [round(it.get("score", 0.0), 4) for it in top[:5]]
            logger.info(
                "RANKING_DONE",
                extra=X(
                    step="rank",
                    selected=len(top),
                    top_n=TOP_N,
                    top5_scores=top_scores,
                    elapsed_ms=round((time.perf_counter() - t_rank) * 1000),
                ),
            )
            if logger.isEnabledFor(10) and top:  # DEBUG
                sample = [
                    {"score": round(it.get("score", 0.0), 4), "title": (it.get("title") or "")[:120], "url": it.get("url", "")}
                    for it in top[:3]
                ]
                logger.debug("RANK_SAMPLE", extra=X(step="rank", sample=sample))

            # --- Summarize ---
            t_summary = time.perf_counter()
            summary_errors = 0
            try:
                top = summarize_items(top)
                # Count items missing summary fields (if summarizer is partial)
                missing_plain = sum(1 for it in top if not it.get("summary"))
                logger.info(
                    "SUMMARY_OK",
                    extra=X(
                        step="summary",
                        count=len(top),
                        missing_summary=missing_plain,
                        elapsed_ms=round((time.perf_counter() - t_summary) * 1000),
                    ),
                )
            except Exception as e:
                summary_errors += 1
                logger.exception("SUMMARY_FAILED", extra=X(step="summary", handled=True, error=type(e).__name__))
                # proceed without summaries if summarization fails

            # --- Persist Articles ---
            t_persist_articles = time.perf_counter()
            persisted_ids: List[int] = []
            persist_errors = 0
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
                except Exception as e:
                    persist_errors += 1
                    logger.exception(
                        "PERSIST_ARTICLE_FAILED",
                        extra=X(step="persist_articles", handled=True, url=it.get("url", ""), error=type(e).__name__),
                    )

            logger.info(
                "ARTICLES_PERSISTED",
                extra=X(
                    step="persist_articles",
                    count=len(persisted_ids),
                    errors=persist_errors,
                    elapsed_ms=round((time.perf_counter() - t_persist_articles) * 1000),
                ),
            )

            # --- Persist Issue ---
            t_issue = time.perf_counter()
            issue_items = [{k: v for k, v in it.items() if k != "content"} for it in top]
            issue_json: Dict[str, Any] = {"date": date, "items": issue_items}

            try:
                s.add(DailyIssue(date=date, items_json=issue_json))
                s.commit()
                logger.info(
                    "ISSUE_PERSISTED",
                    extra=X(
                        step="persist_issue",
                        date=date,
                        items=len(issue_items),
                        elapsed_ms=round((time.perf_counter() - t_issue) * 1000),
                    ),
                )
            except Exception as e:
                logger.exception("PERSIST_ISSUE_FAILED", extra=X(step="persist_issue", handled=True, date=date, error=type(e).__name__))

            # --- Generate & Save PDF (overwrite each run) ---
            t_pdf = time.perf_counter()
            try:
                # ensure output folder exists
                PDF_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                pdf_bytes = render_issue_pdf(issue_json)
                PDF_OUTPUT_PATH.write_bytes(pdf_bytes)  # overwrite
                logger.info(
                    "PDF_SAVED",
                    extra=X(
                        step="pdf_save",
                        path=str(PDF_OUTPUT_PATH.resolve()),
                        size_kb=len(pdf_bytes) // 1024,
                        elapsed_ms=round((time.perf_counter() - t_pdf) * 1000),
                    ),
                )
            except Exception as e:
                logger.exception("PDF_SAVE_FAILED", extra=X(step="pdf_save", handled=True, error=type(e).__name__))

            logger.info(
                "RUN_DAILY_SUCCESS",
                extra=X(
                    step="end",
                    handled=True,
                    total_elapsed_ms=round((time.perf_counter() - t0) * 1000),
                    metrics={
                        "fetch_count": len(raw),
                        "classify_errors": classify_errors,
                        "score_errors": score_errors,
                        "summary_errors": summary_errors,
                        "persist_article_errors": persist_errors,
                        "persisted_articles": len(persisted_ids),
                        "issue_items": len(issue_items),
                        "pdf_path": str(PDF_OUTPUT_PATH.resolve()),
                    },
                ),
            )
            return issue_json

    except Exception as e:
        logger.exception(
            "RUN_DAILY_FATAL",
            extra=X(
                step="fatal",
                handled=False,
                error=type(e).__name__,
                total_elapsed_ms=round((time.perf_counter() - t0) * 1000),
            ),
        )
        raise
