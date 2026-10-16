"""Appeal deadlines (from appeal_rules.csv) and adjustment group codes (from group_codes.csv)."""
import csv
from datetime import date
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"


def _load_rules() -> list[dict]:
    rows = []
    with open(_DATA / "appeal_rules.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("deadline_days") or "").strip().isdigit():
                rows.append({**r, "deadline_days": int(r["deadline_days"]), "verified": (r.get("verified_by_you") or "").strip().upper().startswith("YES")})
    return rows


def _load_groups() -> dict[str, dict]:
    out = {}
    lines = (_DATA / "group_codes.csv").read_text(encoding="utf-8").splitlines()[1:]
    for ln in lines:  # the meaning column contains unquoted commas, so split on the first two commas only
        parts = ln.split(",", 2)
        if len(parts) == 3:
            out[parts[0].strip().upper()] = {"code": parts[0].strip().upper(), "name": parts[1].strip(), "meaning": parts[2].strip()}
    return out


RULES = _load_rules()
GROUPS = _load_groups()
BASELINE = next((r for r in RULES if r["payer"].lower().startswith("federal")), {"deadline_days": 180, "payer": "Federal baseline", "verified": False})


def rule_for(payer: str) -> dict:
    p = (payer or "").lower()
    for r in RULES:
        if not r["payer"].lower().startswith("federal") and r["payer"].lower().split()[0] in p:
            return r
    return BASELINE


def deadline(payer: str, denied_on: str) -> dict:
    """Days left to appeal. `verified` is False until the rule row is marked verified in the CSV."""
    r = rule_for(payer)
    try:
        age = (date.today() - date.fromisoformat((denied_on or "")[:10])).days
        left = r["deadline_days"] - age
    except ValueError:
        left = None
    return {"days_left": left, "window_days": r["deadline_days"], "basis": r.get("deadline_basis") or r.get("plan_type") or "",
            "rule": r["payer"], "verified": r["verified"]}


def group_info(code: str) -> dict | None:
    return GROUPS.get((code or "").strip().upper())
