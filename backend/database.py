"""Thin SQL helper layer on SQLAlchemy 2.0 (works on SQLite and PostgreSQL).

Keeps the small `q / q1 / ex` API the routers use. SQL is written with `?` placeholders and
translated to named bind parameters here, so routers stay readable and portable.
"""
import re
from contextlib import contextmanager

import sqlalchemy as sa

from . import config
from .models import metadata

_kwargs: dict = {"pool_pre_ping": True, "future": True}
if config.IS_SQLITE:
    _kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
engine = sa.create_engine(config.DATABASE_URL, **_kwargs)
if config.IS_SQLITE:
    @sa.event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # enforce ON DELETE CASCADE on SQLite
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

NO_ID_TABLES = {"revoked_tokens", "icd_cache"}


def _bind(sql: str, args):
    i = -1

    def rep(_):
        nonlocal i
        i += 1
        return f":p{i}"
    text = re.sub(r"\?", rep, sql)
    if not config.IS_SQLITE:
        text = re.sub(r"INSERT OR IGNORE", "INSERT", text, flags=re.I) if "INSERT OR IGNORE" in text.upper() else text
        if "INSERT OR IGNORE" in sql.upper():
            text += " ON CONFLICT DO NOTHING"
    return sa.text(text), {f"p{k}": v for k, v in enumerate(args)}


@contextmanager
def conn():
    with engine.begin() as c:
        yield c


def init_db() -> None:
    """Create tables if missing. Production uses `alembic upgrade head`; this keeps dev/tests zero-config."""
    metadata.create_all(engine)


def q(sql, args=()):
    stmt, params = _bind(sql, args)
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(stmt, params).fetchall()]


def q1(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def ex(sql, args=()):
    stmt, params = _bind(sql, args)
    is_insert = sql.lstrip().upper().startswith("INSERT")
    table = re.search(r"INTO\s+(\w+)", sql, re.I)
    wants_id = is_insert and not (table and table.group(1).lower() in NO_ID_TABLES)
    if wants_id and not config.IS_SQLITE:
        stmt = sa.text(str(stmt) + " RETURNING id")
    with engine.begin() as c:
        res = c.execute(stmt, params)
        if wants_id:
            return res.scalar() if not config.IS_SQLITE else res.lastrowid
        return None
