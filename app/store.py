"""
store.py
========
This module is the *database gateway* for the app.

It does three things:
1) Creates a connection "engine" to the database.
2) Creates tables (once) based on your SQLModel classes in models.py.
3) Provides a helper to open a database "Session" (a unit of work/transaction).
"""

from sqlmodel import SQLModel, Session, create_engine
from typing import Generator
import os

# In a small project, a SQLite database file in the project root is simple and reliable.
# The URL "sqlite:///quantum_daily.db" means:
#   - "sqlite" driver
#   - "///" local file path (relative to current working directory)
#   - "quantum_daily.db" is the file name
#
# If you later move to Postgres, this string becomes something like:
#   "postgresql+psycopg2://user:password@host:5432/your_db"
#
# TIP: You can pull this from config.py if you prefer, e.g.:
#   from .config import DB_URL
#   engine = create_engine(DB_URL, echo=False)
#
# echo=False turns off SQL logging. Set echo=True during debugging to see SQL statements.
DB_FILE = os.getenv("DB_FILE", "quantum_daily.db")
DB_URL = f"sqlite:///{DB_FILE}"

# The engine is the "connection factory" and pool. You create it once and reuse it.
# For SQLite, this will create the file on first write if it doesn't exist.
engine = create_engine(DB_URL, echo=False)


def init_db() -> None:
    """
    Create all database tables based on the SQLModel classes you defined in models.py.

    How it works in plain English:
    - You define Python classes like Article, DailyIssue that inherit from SQLModel and set table=True.
    - SQLModel collects their metadata (table names, columns, types).
    - This call translates those class definitions into CREATE TABLE statements (if tables don't exist yet).
    - It is safe to call on every startup; it won't drop data. It only creates missing tables.
    """
    # Import your models here (inside the function) so Python loads them *before*
    # create_all() runs. If you import at top-level, it's also fine as long as there
    # are no circular imports. This pattern avoids surprises.
    from . import models  # noqa: F401  (import just to register models with SQLModel)

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Open a database Session bound to our engine.

    A Session is:
    - Your "workspace" for talking to the DB.
    - It keeps track of objects you add/update/delete.
    - It groups operations into a transaction. When you call session.commit(), your changes
      are flushed to the database atomically.

    Usage pattern:
      with get_session() as session:
          session.add(obj)
          session.commit()
          # optional: session.refresh(obj) to populate generated fields (like auto-increment id)

    Why use a function?
    - Centralizes the session creation. If you ever change DB config, only update here.
    - Encourages proper open/close lifecycle (the 'with' block closes it even on errors).
    """
    return Session(engine)
