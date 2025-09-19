from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime

class Article(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    title: str
    content: Optional[str] = ""
    published_at: Optional[datetime] = None
    source: Optional[str] = ""
    topics: List[str] = Field(default_factory=list, sa_column=Column(JSON))

class DailyIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str  # YYYY-MM-DD
    items_json: dict = Field(default_factory=dict, sa_column=Column(JSON))

class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int
    signal: str  # +1, -1, more, less
    aspect: str  # industry, tech, source:<>, topic:<>
    ts: datetime = Field(default_factory=datetime.utcnow)

class UserPrefs(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    industry_weight: float = 0.7
    tech_weight: float = 0.3
    email: str = ""
    send_hour_local: int = 8
    source_bias: dict = Field(default_factory=dict, sa_column=Column(JSON))
    topic_bias: dict = Field(default_factory=dict, sa_column=Column(JSON))
