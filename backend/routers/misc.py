"""Public endpoints: site content, live stats, dropdown sources, health, eligibility check, contact form."""
import json
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends

from .. import config
from .. import database as db
from .. import security as sec
from ..schemas import ContactIn, EligibilityIn
from ..services import denial_codes, predictor, rag
from ..services.audit import audit
from ..services.files import ocr_available
from ..services.mail import mail_enabled, send_mail

router = APIRouter(prefix="/api", tags=["public"])
_CONTENT = json.loads((Path(__file__).resolve().parent.parent / "data" / "site_content.json").read_text(encoding="utf-8"))
VERSION = "2.0.0"


@router.get("/site/content")
def site_content():
    return _CONTENT


@router.get("/public/stats")
def public_stats():
    appeals = db.q1("SELECT COUNT(*) AS n, AVG(win_probability) AS avg FROM appeals")
    pols = db.q("SELECT content FROM policies WHERE org_id IS NULL")
    chunks = sum(len(rag.chunk_text(p["content"])) for p in pols)
    return {"codes": len(denial_codes.CARC_DESC) + len(denial_codes.RARC_DESC) + len(denial_codes.EOB), "carc": len(denial_codes.CARC_DESC),
            "rarc": len(denial_codes.RARC_DESC), "eob": len(denial_codes.EOB), "policies": len(pols), "policy_chunks": chunks,
            "appeals": appeals["n"], "avg_win_probability": round(appeals["avg"], 3) if appeals["avg"] is not None else None}


@router.get("/payers")
def payers():
    rows = db.q("SELECT DISTINCT payer FROM policies WHERE org_id IS NULL")
    return {"payers": sorted(r["payer"] for r in rows if r["payer"].upper() not in ("ALL", "GENERAL"))}


@router.get("/procedures")
def procedures(q: str = ""):
    ql = q.lower().strip()
    items = [{"code": k, "description": v} for k, v in denial_codes.CPT.items() if not ql or ql in k or ql in v.lower()]
    return {"procedures": items[:25]}


@router.get("/health")
def health():
    chunks = sum(len(rag.chunk_text(p["content"])) for p in db.q("SELECT content FROM policies"))
    model = predictor.get_model()
    return {"status": "ok", "version": VERSION, "db": "sqlite" if config.IS_SQLITE else "postgresql",
            "integrations": {"ai": bool(config.llm_provider()), "ai_provider": config.llm_provider(), "ai_model": config.llm_model(), "mail": mail_enabled(), "google": bool(config.GOOGLE_CLIENT_ID), "fhir": config.FHIR_ENABLED,
                             "ocr": ocr_available(), "embeddings": rag.embeddings_active(), "deidentify": config.DEIDENTIFY_BEFORE_LLM, "require_verified": config.REQUIRE_VERIFIED},
            "policy_chunks": chunks, "model": {"kind": model.get("kind", "synthetic"), "n": model.get("n", 0)}}


@router.post("/public/eligibility", dependencies=[Depends(sec.rate_limit("elig", 30))])
def eligibility(body: EligibilityIn):
    d = denial_codes.info(body.denial_code or "50")
    coverage = 0.55 if body.has_records else 0.2
    denied_on = (date.today() - timedelta(days=body.days_since_denial)).isoformat()
    p = predictor.predict(d["base_win"], coverage, 0.5, body.has_records, denied_on, body.amount)
    window = 180 - body.days_since_denial
    if not d["appealable"]:
        verdict, label = "unlikely", "Usually not appealable"
    elif p["probability"] >= 0.55:
        verdict, label = "strong", "Strong case to appeal"
    elif p["probability"] >= 0.35:
        verdict, label = "possible", "Worth appealing with good documentation"
    else:
        verdict, label = "weak", "Harder case, appeal only with strong evidence"
    return {"verdict": verdict, "label": label, "probability": p["probability"], "denial": d, "days_left": window, "model_kind": p["model_kind"],
            "next_steps": [d["strategy"], "Ask the payer for the exact policy that was used to deny the service.",
                           "Bring your records into a Pramaan AI appeal to map them to the policy." if body.has_records else "Collect your doctor's notes and test results.",
                           f"Many payers allow about 180 days to appeal. Roughly {max(window, 0)} days left on that baseline (confirm your plan's deadline)."]}


@router.post("/contact", status_code=201, dependencies=[Depends(sec.rate_limit("contact", 5))])
def contact(body: ContactIn):
    emailed = send_mail(config.CONTACT_TO, f"[Pramaan AI] {body.kind} message from {body.name}", f"From: {body.name} <{body.email}>\nType: {body.kind}\n\n{body.message}") if config.CONTACT_TO else False
    db.ex("INSERT INTO contact_messages(name,email,kind,message,emailed) VALUES(?,?,?,?,?)", (body.name, str(body.email).lower(), body.kind, body.message, 1 if emailed else 0))
    audit(None, "contact_message", body.kind)
    return {"message": "Thanks. Your message was received.", "emailed": emailed}
