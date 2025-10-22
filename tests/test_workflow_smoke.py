# tests/test_workflow_smoke.py
from freezegun import freeze_time

def test_run_daily_smoke(mocker):
    # Avoid live HTTP + OpenAI calls
    mocker.patch("app.sources.fetch_all", return_value=[
        {"url":"u1","title":"A","content":"biz","published_at":None,"source":"S"}
    ])
    mocker.patch("app.summarize.summarize_items", side_effect=lambda xs: [{**x, "summary":"ok"} for x in xs])
    mocker.patch("app.render_issue.render_issue_pdf", return_value=b"%PDF-1.4 fake")
    mocker.patch("pathlib.Path.write_bytes", return_value=None)

    from app.workflow import run_daily, TOP_N
    with freeze_time("2025-01-01"):
        issue = run_daily()
    assert "items" in issue and len(issue["items"]) <= TOP_N
    assert issue["items"][0]["summary"] == "ok"
