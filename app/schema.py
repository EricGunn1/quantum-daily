from pydantic import BaseModel
from typing import List, Optional

class FeedbackIn(BaseModel):
    article_id: int
    signal: str       # +1 | -1 | more | less
    aspect: str       # industry | tech | source:NAME | topic:TAG

class PrefsIn(BaseModel):
    industry_weight: Optional[float] = None
    tech_weight: Optional[float] = None
    email: Optional[str] = None
    send_hour_local: Optional[int] = None
