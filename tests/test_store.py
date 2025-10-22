# tests/test_store.py
from sqlmodel import select
from app.store import get_session
from app.models import Article

def test_db_roundtrip():
    with get_session() as s:
        a = Article(url="u", title="t")
        s.add(a); s.commit(); s.refresh(a)
        got = s.exec(select(Article).where(Article.id == a.id)).first()
        assert got and got.title == "t"
