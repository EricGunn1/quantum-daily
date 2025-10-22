# tests/test_ranker.py
from app.ranker import classify_industry_vs_tech, composite_score
from app.models import UserPrefs

def test_classify_industry_biases_business_text():
    it = {"title": "IonQ signs enterprise deal", "content": "revenue, partnership, customer"}
    cls = classify_industry_vs_tech(it)
    assert 0 <= cls["industry"] <= 1 and 0 <= cls["tech"] <= 1
    assert cls["industry"] >= cls["tech"]

def test_composite_score_respects_prefs():
    prefs = UserPrefs(industry_weight=0.8, tech_weight=0.2)
    s_ind = composite_score({"title":"X","category":"industry"}, {"industry":0.8,"tech":0.2}, prefs)
    s_tech = composite_score({"title":"Y","category":"tech"}, {"industry":0.2,"tech":0.8}, prefs)
    assert s_ind > s_tech
