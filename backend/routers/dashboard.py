"""Dashboard analytics with date-range and payer filters."""
from collections import Counter, defaultdict
from datetime import date

from fastapi import APIRouter, Depends

from .. import database as db
from .. import security as sec
from ..services import deadlines, predictor
from ..services.denial_codes import CATEGORY_LABEL

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _months(n: int = 6) -> list[str]:
    t, out = date.today(), []
    for i in range(n - 1, -1, -1):
        y, m = t.year, t.month - i
        while m <= 0:
            m, y = m + 12, y - 1
        out.append(f"{y}-{m:02d}")
    return out


@router.get("")
def stats(date_from: str = "", date_to: str = "", payer: str = "", user: dict = Depends(sec.current_user)):
    where, args = ["user_id=?"], [user["id"]]
    if payer:
        where.append("payer=?"); args.append(payer)
    if date_from:
        where.append("denied_on>=?"); args.append(date_from)
    if date_to:
        where.append("denied_on<=?"); args.append(date_to)
    claims = db.q("SELECT * FROM claims WHERE " + " AND ".join(where), args)
    ids = {c["id"] for c in claims}
    appeals = [a for a in db.q("SELECT * FROM appeals WHERE user_id=?", (user["id"],)) if a["claim_id"] in ids]
    cmap = {c["id"]: c for c in claims}
    amt = lambda c: float(c["denied_amount"] or c["billed_amount"] or 0)  # noqa: E731
    decided = [a for a in appeals if a["status"] in ("won", "partial", "lost")]
    wins = [a for a in decided if a["status"] in ("won", "partial")]
    open_claims = [c for c in claims if c["status"] in ("denied", "appeal_ready", "appealed")]
    avg_secs = round(sum(a["gen_seconds"] or 0 for a in appeals) / len(appeals), 2) if appeals else 0

    months = _months()
    denied_m, rec_m = defaultdict(float), defaultdict(float)
    for c in claims:
        denied_m[(c["denied_on"] or c["created_at"] or "")[:7]] += amt(c)
    for a in appeals:
        if a["recovered_amount"]:
            rec_m[(a["updated_at"] or a["created_at"] or "")[:7]] += a["recovered_amount"]

    cat_stats: dict[str, dict] = defaultdict(lambda: {"won": 0, "decided": 0, "claims": 0})
    for c in claims:
        cat_stats[c["denial_category"] or "unknown"]["claims"] += 1
    for a in decided:
        k = cmap[a["claim_id"]]["denial_category"] or "unknown"
        cat_stats[k]["decided"] += 1
        cat_stats[k]["won"] += 1 if a["status"] in ("won", "partial") else 0
    top = Counter(c["denial_code"] or "?" for c in claims).most_common(6)
    exposure: dict[str, float] = defaultdict(float)
    for c in open_claims:
        exposure[c["payer"]] += amt(c)
    urgent = []
    for c in open_claims:
        d = deadlines.deadline(c["payer"], c["denied_on"])
        if d["days_left"] is not None:
            urgent.append({"id": c["id"], "claim_no": c["claim_no"], "patient_name": c["patient_name"], "days_left": d["days_left"], "amount": amt(c), "verified": d["verified"]})
    urgent.sort(key=lambda x: x["days_left"])
    model = predictor.get_model()
    return {
        "totals": {"claims": len(claims), "denied_value": round(sum(amt(c) for c in claims), 2), "at_risk_value": round(sum(amt(c) for c in open_claims), 2),
                   "appeals": len(appeals), "decided": len(decided), "win_rate": round(len(wins) / len(decided), 3) if decided else None,
                   "recovered": round(sum(a["recovered_amount"] or 0 for a in appeals), 2), "avg_generation_seconds": avg_secs,
                   "pending_appeals": len([c for c in claims if c["status"] == "denied"])},
        "by_status": dict(Counter(c["status"] for c in claims)),
        "monthly": [{"month": m, "denied": round(denied_m.get(m, 0), 2), "recovered": round(rec_m.get(m, 0), 2)} for m in months],
        "win_by_category": [{"category": CATEGORY_LABEL.get(k, k), "claims": v["claims"], "decided": v["decided"], "win_rate": round(v["won"] / v["decided"], 3) if v["decided"] else None}
                            for k, v in cat_stats.items()],
        "top_codes": [{"code": k, "count": v} for k, v in top],
        "payer_exposure": sorted([{"payer": k, "amount": round(v, 2)} for k, v in exposure.items()], key=lambda x: -x["amount"])[:6],
        "deadlines": urgent[:6],
        "payers": sorted({c["payer"] for c in db.q("SELECT DISTINCT payer FROM claims WHERE user_id=?", (user["id"],))}),
        "model": {"kind": model.get("kind", "synthetic"), "n": model.get("n", 0), "min_outcomes": predictor.MIN_OUTCOMES},
    }
