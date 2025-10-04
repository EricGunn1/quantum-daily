from __future__ import annotations
from typing import Dict, Any, List
from html import escape
from urllib.parse import urlparse

def _domain(u: str) -> str:
    try:
        return urlparse(u).netloc or ""
    except Exception:
        return ""

def render_issue_html(issue: Dict[str, Any]) -> str:
    date = escape(issue.get("date", ""))
    items: List[Dict[str, Any]] = issue.get("items", [])

    rows = []
    for it in items:
        title = escape(it.get("title", "") or "")
        url = it.get("url", "") or "#"
        domain = escape(_domain(url))
        # support both your legacy "summary" and the newer "plain_summary"
        summary = escape(it.get("plain_summary") or it.get("summary") or "")
        bullets = it.get("tldr_bullets") or []
        bullets_html = "".join(f"<li>{escape(b)}</li>" for b in bullets[:3]) if bullets else ""

        rows.append(f"""
        <article class="card">
          <h2><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>
          <div class="meta">{domain}</div>
          <p class="summary">{summary}</p>
          {f"<ul class='tldr'>{bullets_html}</ul>" if bullets_html else ""}
        </article>
        """)

    body = "\n".join(rows) or "<p>No items found.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Quantum Daily — {date}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
  header {{ margin-bottom: 20px; }}
  .card {{ padding: 16px; margin: 12px 0; border: 1px solid #eee; border-radius: 12px; }}
  .card h2 {{ margin: 0 0 6px 0; font-size: 1.1rem; }}
  .card .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 8px; }}
  .card .summary {{ margin: 8px 0 0 0; line-height: 1.4; }}
  .tldr {{ margin: 8px 0 0 18px; }}
</style>
</head>
<body>
  <header>
    <h1>Quantum Daily — {date}</h1>
    <nav><a href="/docs">API docs</a></nav>
  </header>
  {body}
</body>
</html>"""
