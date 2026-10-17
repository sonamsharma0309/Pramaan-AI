"""Loads the bundled payer policies into the shared policy library (idempotent)."""
from pathlib import Path

from .. import database as db

POLICY_DIR = Path(__file__).resolve().parent / "policies"


def seed_policies():
    for f in sorted(POLICY_DIR.glob("*.txt")):
        raw = f.read_text(encoding="utf-8").strip().splitlines()
        payer = raw[0].split(":", 1)[1].strip()
        title = raw[1].split(":", 1)[1].strip()
        body = "\n".join(raw[2:]).strip()
        if not db.q1("SELECT 1 FROM policies WHERE user_id IS NULL AND title=?", (title,)):
            db.ex("INSERT INTO policies(user_id,payer,title,content) VALUES(NULL,?,?,?)", (payer, title, body))
