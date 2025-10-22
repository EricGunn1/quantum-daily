# tests/test_summarize.py
def test_summarize_items_injects_summary(mocker):
    # whatever function your code calls per item—adapt the import path if needed
    mocker.patch("app.summarize._summarize_one", return_value={"summary": "ok"})
    from app.summarize import summarize_items
    items = [{"title": "Foo", "url": "http://u"}]
    out = summarize_items(items)
    assert out and out[0]["summary"] == "ok"
