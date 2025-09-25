from typing import List, Dict
from app.config import client as OPENAI_API_KEY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYS_PROMPT = """You are a concise news summarizer. Output 2-4 sentences.
Label each item as 'industry' or 'tech' based on commercial vs. research/engineering focus.
Be concrete. Avoid hype. Include specific companies/partners/funding/products if present.
"""

def summarize_items(items: List[Dict]) -> List[Dict]:
    if not client:
        # Dev fallback without LLM
        for it in items:
            it["summary"] = (it.get("content") or it["title"])[:280]
            it["category"] = "industry" if "partner" in (it["title"]+it.get("content","")).lower() else "tech"
        return items

    for it in items:
        content = f"Title: {it['title']}\nSource: {it['source']}\nText: {it.get('content','')[:4000]}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYS_PROMPT},
                      {"role":"user","content":content}],
            temperature=0.2
        )
        txt = resp.choices[0].message.content.strip()
        it["summary"] = txt
        # naive tag—could parse from model output; we also have classifier in ranker
    return items
