from typing import List, Dict
from openai import OpenAI
from .config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

SYS = "You write 2-3 sentence, concrete news summaries. No fluff."

def summarize_items(items: List[Dict]) -> List[Dict]:
    # Summarize each item individually; simple and robust.
    for it in items:
        prompt = f"Title: {it['title']}\nSource: {it['source']}\nText: {it.get('content','')[:1500]}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYS},
                      {"role":"user","content":prompt}],
            temperature=0.2,
        )
        it["summary"] = resp.choices[0].message.content.strip()
        # rough tag (we'll improve later)
        t = (it["title"] + " " + it.get("content","")).lower()
        it["category"] = "industry" if any(k in t for k in ["partnership","funding","deal","acquisition","launch"]) else "tech"
    return items
