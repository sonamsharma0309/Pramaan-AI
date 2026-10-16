"""End-to-end analysis for one denied claim: denial -> policy RAG -> evidence -> win estimate -> deadline."""
from .. import database as db
from . import deadlines, predictor, rag
from . import evidence as ev
from .denial_codes import CATEGORY_KEYWORDS, info

CATEGORY_DOCS = {
    "authorization": "Authorization / referral number, or a retro-authorization request with clinical urgency",
    "timely_filing": "Clearinghouse acceptance report proving timely submission",
    "administrative": "Corrected claim form / missing fields identified in the remark code",
    "coding": "Corrected CPT/ICD-10 coding or modifier with coder sign-off",
    "eligibility": "Proof of active coverage on the date of service",
}


def applicable_policies(user: dict, payer: str) -> list[dict]:
    """Policies visible to this user: the read-only shared library plus their own organisation's uploads."""
    rows = db.q("SELECT * FROM policies WHERE org_id IS NULL OR org_id=?", (user.get("org_id"),))
    return [p for p in rows if rag.payer_matches(p["payer"], payer)]


def analyze(claim: dict, user: dict) -> dict:
    d = info(claim.get("denial_code", ""))
    policies = applicable_policies(user, claim.get("payer", ""))
    query = " ".join(filter(None, [claim.get("denial_reason", ""), claim.get("procedure_desc", ""), claim.get("procedure_code", ""),
                                    claim.get("diagnosis", ""), CATEGORY_KEYWORDS.get(d["category"], "")]))
    hits = rag.retrieve(query, policies, k=4, boost_terms=[claim.get("procedure_code", "")])
    # A hit only counts as a policy for this service if it is reasonably relevant (guards against a weak accidental match).
    relevant = [h for h in hits if h["score"] >= 0.08]
    # "ALL" policies are generic appeal standards; they do not count as a payer policy for this service.
    specific = [h for h in relevant if h["payer"].upper() not in ("ALL", "GENERAL")]
    notes = claim.get("ehr_notes", "") or ""
    res = ev.analyse(notes, specific, query)  # criteria come only from payer-specific policies, never the generic appeal standards
    pm = rag.policy_match_score(specific)
    amount = float(claim.get("denied_amount") or claim.get("billed_amount") or 0)
    pred = predictor.predict(d["base_win"], res["coverage"], pm, bool(notes.strip()), claim.get("denied_on", ""), amount)
    missing = []
    if not notes.strip():
        missing.append("Clinical notes from the patient's EHR chart (upload or paste them)")
    missing += [f"Evidence for policy criterion: {c['text'][:160]}" for c in res["criteria"] if c["status"] == "missing"]
    if d["category"] in CATEGORY_DOCS:
        missing.append(CATEGORY_DOCS[d["category"]])
    if not specific:
        missing.append("No matching payer policy found. Upload this payer's medical policy in the Policy library")
    return {
        "denial": d, "policy_hits": relevant, "evidence": res["evidence"], "criteria": res["criteria"], "coverage": res["coverage"],
        "policy_match": round(pm, 3), "icd": res["icd"], "prediction": pred, "missing_docs": missing[:8], "policies_searched": len(policies),
        "no_policy": not specific, "deadline": deadlines.deadline(claim.get("payer", ""), claim.get("denied_on", "")),
        "group": deadlines.group_info(claim.get("group_code", "")), "embeddings": rag.embeddings_active(),
    }
