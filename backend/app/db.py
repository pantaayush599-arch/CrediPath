"""Database engine and session.

Uses ``DATABASE_URL`` when set (e.g. a Supabase Postgres connection string,
``postgresql+psycopg://user:pass@host:5432/postgres``); otherwise a local
SQLite file at ``backend/data/credipath.db``. On Vercel (read-only filesystem
except /tmp) the SQLite fallback lives in /tmp and is reset on every cold start,
so a real deployment should set ``DATABASE_URL``.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Bundled, read-only assets (sample CSVs) ship with the code.
ASSETS_DIR = BACKEND_DIR / "data"
ON_VERCEL = bool(os.environ.get("VERCEL"))
# Writable location for the SQLite fallback.
DATA_DIR = Path("/tmp/credipath") if ON_VERCEL else ASSETS_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DATA_DIR / 'credipath.db'}"
    # Supabase / Heroku style URLs -> SQLAlchemy psycopg3 driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def backend_label() -> str:
    if IS_SQLITE:
        return "SQLite (local fallback)"
    host = DATABASE_URL.split("@")[-1].split("/")[0]
    return f"PostgreSQL ({'Supabase' if 'supabase' in host else host.split(':')[0]})"


def get_session():
    from .services.seed import ensure_ready  # local import avoids a cycle

    ensure_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
