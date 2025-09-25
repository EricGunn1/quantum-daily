from datetime import datetime, timezone
from typing import Dict, List
import math

def classify_industry_vs_tech(item) -> Dict[str, float]:
    t = (item["title"] + " " + item.get("content","")).lower()
    industry_kws = ["partnership","funding","acquisition","deal","deploy","product","roadmap",
                    "market","customer","commercial","hiring","announcement","launch"]
    tech_kws = ["qubit","error rate","decoherence","benchmark","algorithm","architecture",
                "compiler","gate","circuit","fault-tolerant","paper","arxiv"]

    i_score = sum(k in t for k in industry_kws)
    t_score = sum(k in t for k in tech_kws)
    # softmax-ish normalize
    total = i_score + t_score + 1e-6
    return {"industry": i_score/total, "tech": t_score/total}

def composite_score(item, cls, prefs, now=None):
    now = now or datetime.now(timezone.utc)
    recency_hours = 1.0 / max(1.0, ((now - (item["published_at"] or now)).total_seconds()/3600.0))
    recency_bonus = 0.10 * math.log10(1 + recency_hours)

    source_bias = prefs.source_bias.get(item["source"], 0.0)
    topic_bias = 0.0
    for topic in ["industry","tech"]:
        topic_bias += prefs.topic_bias.get(topic, 0.0) * cls[topic]

    base = prefs.industry_weight * cls["industry"] + prefs.tech_weight * cls["tech"]
    return base + source_bias + topic_bias + recency_bonus

def apply_feedback(prefs, fb_list, lr=0.05):
    for fb in fb_list:
        sig = fb.signal
        asp = fb.aspect
        if asp in ("industry","tech"):
            delta = (1 if sig in ("+1", "more") else -1 if sig in ("-1","less") else 0) * lr
            if asp == "industry":
                prefs.industry_weight = min(1.0, max(0.0, prefs.industry_weight + delta))
                prefs.tech_weight = 1.0 - prefs.industry_weight
            else:
                prefs.tech_weight = min(1.0, max(0.0, prefs.tech_weight + delta))
                prefs.industry_weight = 1.0 - prefs.tech_weight
        elif asp.startswith("source:"):
            name = asp.split(":",1)[1]
            prefs.source_bias[name] = prefs.source_bias.get(name, 0.0) + (lr if sig in ("+1","more") else -lr)
        elif asp.startswith("topic:"):
            name = asp.split(":",1)[1]
            prefs.topic_bias[name] = prefs.topic_bias.get(name, 0.0) + (lr if sig in ("+1","more") else -lr)
    # light clamp of biases
    for d in (prefs.source_bias, prefs.topic_bias):
        for k,v in list(d.items()):
            d[k] = max(-0.5, min(0.5, v))
    return prefs
