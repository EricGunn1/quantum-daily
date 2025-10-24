# app/routers/summary.py
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlmodel import select
from datetime import datetime
from pathlib import Path
from collections import Counter
import re

from ..logging_setup import get_logger
from ..store import get_session
from ..models import DailyIssue
from ..workflow import run_daily
from ..render_issue import render_issue_html, render_issue_pdf

# --- add near the top of summary.py (after imports) ---
PAGE_CSS = """
body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:24px;}
h1{margin:0 0 12px;}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:14px;margin:12px 0;}
.meta{color:#6b7280;font-size:12px;margin-top:4px}
.btnbar{margin-top:8px;display:flex;gap:8px;flex-wrap:wrap}
.btn{border:1px solid #d1d5db;border-radius:8px;padding:4px 8px;text-decoration:none;cursor:pointer;background:#fff;}
.btn:hover{background:#f3f4f6}
.toast{position:fixed;right:16px;bottom:16px;background:#111827;color:#fff;padding:10px 12px;border-radius:8px;opacity:0;transition:opacity .2s}
.toast.show{opacity:0.92}
hr{border:none;border-top:1px solid #eee;margin:16px 0}
small.code{font-family:ui-monospace, SFMono-Regular, Menlo, monospace;color:#6b7280}
"""

PAGE_JS = """
async function sendFB(articleId, signal, aspect){
  try{
    const res = await fetch('/feedback', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({article_id: articleId, signal, aspect})
    });
    const ok = res.ok;
    const data = await res.json().catch(()=>({}));
    showToast(ok ? 'Feedback saved' : ('Error: ' + (data.detail || res.status)));
    // Optionally refresh the prefs readout after a successful save
    if(ok) loadPrefs();
  }catch(e){
    showToast('Network error');
  }
}
let toast;
function showToast(msg){
  if(!toast){ toast = document.querySelector('.toast'); }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(()=>toast.classList.remove('show'), 1400);
}
async function loadPrefs(){
  try{
    const r = await fetch('/prefs'); if(!r.ok) return;
    const p = await r.json();
    const s = `industry_weight=${(p.industry_weight||0).toFixed(2)} · tech_weight=${(p.tech_weight||0).toFixed(2)}`;
    document.getElementById('prefs').textContent = s;
  }catch{}
}
"""

def _esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

_STOP = set("""
a an and the of for to in on with by as at from about via into over under toward against between among
is are be was were been being this that those these it its their his her our your they we you i
new more less very most least not no yes will would can could should may might
""".split())

def _overview(items):
    """Compute quick trends/commonalities from today's items."""
    n = len(items)
    cat = Counter((it.get("category") or "").lower() for it in items)
    sources = Counter(it.get("source") or "Unknown" for it in items)

    # rough topics from title + content
    words = Counter()
    for it in items:
        text = f"{it.get('title','')} {it.get('content','')}"
        text = re.sub(r"[^A-Za-z0-9 ]+", " ", text).lower()
        for w in text.split():
            if len(w) < 4 or w in _STOP:
                continue
            words[w] += 1

    top_sources = sources.most_common(3)
    top_topics = [w for w, _ in words.most_common(5)]

    parts = []
    if n:
        parts.append(f"{n} items")
    if cat.get("industry") or cat.get("tech"):
        parts.append(f"{cat.get('industry',0)} industry / {cat.get('tech',0)} tech")
    if top_sources:
        parts.append("top sources: " + ", ".join(s for s, _ in top_sources))
    if top_topics:
        parts.append("top topics: " + ", ".join(top_topics[:3]))

    return {
        "n": n,
        "cat": dict(cat),
        "top_sources": top_sources,
        "top_topics": top_topics,
        "summary": " · ".join(parts) if parts else "No items today."
    }


logger = get_logger("quantum_daily.routes.summary")
router = APIRouter(prefix="/summary")

# Anchor PDF path to the repo root so it’s predictable regardless of CWD
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # <repo>/
PDF_OUTPUT_PATH = PROJECT_ROOT / "exports" / "QuantumDaily.pdf"


@router.get("/today")
def get_today(regen: bool = Query(False, description="Force rebuild for today")):
    """
    Return today's issue as JSON. Use ?regen=1 to force a fresh build.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"Fetching daily issue for {today} (regen={regen})")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        issue_json = run_daily() if (regen or not issue) else issue.items_json
    return JSONResponse(issue_json)


@router.post("/run-once")
def run_once():
    """
    Trigger a fresh run right now (always rebuilds today).
    Visible in docs for convenience.
    """
    logger.info("Manual run_once invoked")
    return JSONResponse(run_daily())


@router.get("/today.html", response_class=HTMLResponse)
def get_today_html(regen: bool = Query(False, description="Force rebuild for today")):
    """
    Render today's issue as HTML.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        issue_json = run_daily() if (regen or not issue) else issue.items_json
    return HTMLResponse(render_issue_html(issue_json))


@router.get("/today.pdf")
def get_today_pdf(regen: bool = Query(False, description="Force rebuild & save PDF"), download: bool = Query(True)):
    """
    Generate (and save) today's PDF and return it.
    - Saves/overwrites <repo>/exports/QuantumDaily.pdf on disk every call
    - Set ?regen=1 to rebuild today’s issue before exporting
    - Set ?download=false if you only want it saved on disk (response still streams the file)
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        issue_json = run_daily() if (regen or not issue) else issue.items_json

    # Ensure folder exists and write the PDF (always overwrite)
    PDF_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = render_issue_pdf(issue_json)
    PDF_OUTPUT_PATH.write_bytes(pdf_bytes)

    logger.info("PDF_READY", extra={"path": str(PDF_OUTPUT_PATH.resolve()), "size_kb": len(pdf_bytes) // 1024})

    # Stream the file back; iOS Gmail will let you open/share it
    filename = f"QuantumDaily-{today}.pdf"
    # If download=false, most browsers will still display inline; Gmail will show it as an attachment either way
    return FileResponse(PDF_OUTPUT_PATH, media_type="application/pdf", filename=filename)

@router.get("/today_interactive.html", response_class=HTMLResponse)
def get_today_interactive_html(regen: bool = Query(False, description="Force rebuild for today")):
    """
    Interactive view:
    - Overview of trends/commonalities at the top
    - Overall feedback: 'too industry' / 'too tech' (tilts global weights)
    - Per-article thumbs: 👍/- nudges source bias for that article's source
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_session() as s:
        issue = s.exec(select(DailyIssue).where(DailyIssue.date == today)).first()
        issue_json = run_daily() if (regen or not issue) else issue.items_json

    items = issue_json.get("items", [])
    date = issue_json.get("date", today)
    ov = _overview(items)

    def render_item(it):
        aid = it.get("id") or 0
        title = _esc(it.get("title") or "")
        url = it.get("url") or "#"
        source = _esc(it.get("source") or "Unknown")
        cat = _esc(it.get("category") or "—")
        pub = _esc(str(it.get("published_at") or ""))
        summ = _esc(it.get("summary") or (it.get("content") or "")[:280])
        score = it.get("score")
        score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
        return f"""
        <div class='card'>
          <div style='font-weight:600;font-size:16px'>
            <a href="{url}" target="_blank" rel="noopener">{title}</a>
          </div>
          <div class='meta'>{cat} • {source} • {pub} • score <small>{score_str}</small></div>
          <p style='margin:8px 0 0'>{summ}</p>
          <div class='btnbar'>
            <button class='btn' style="border-color:#10b981"
                    title='thumbs up' onclick="sendFB({aid}, '+1', 'source:{source}')">👍</button>
            <button class='btn' style="border-color:#ef4444"
                    title='thumbs down' onclick="sendFB({aid}, '-1', 'source:{source}')">👎</button>
          </div>
        </div>
        """

    items_html = "\n".join(render_item(it) for it in items) or "<p>No items.</p>"

    page = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Quantum Daily — {date}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
  <h1>Quantum Daily — {date}</h1>

  <!-- Overview & overall feedback -->
  <div class="card" style="background:#fafafa">
    <div style="font-weight:600;margin-bottom:6px">Overview</div>
    <div class="meta" id="prefs">Loading preferences…</div>
    <p style="margin:8px 0 0">{_esc(ov["summary"])}</p>
    <div class="btnbar" style="margin-top:10px">
      <button class="btn" onclick="sendFB(0, 'less', 'industry')">Overall: too industry</button>
      <button class="btn" onclick="sendFB(0, 'less', 'tech')">Overall: too tech</button>
    </div>
    <div class="meta"><small class='code'>These buttons call POST /feedback</small></div>
  </div>

  <hr/>
  {items_html}
  <div class='toast'></div>
<script>{PAGE_JS}</script>
<script>loadPrefs();</script>
</body>
</html>"""
    return HTMLResponse(page)
