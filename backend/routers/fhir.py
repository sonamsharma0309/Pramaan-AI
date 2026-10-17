"""FHIR R4 import of clinical notes (feature-flagged with FHIR_ENABLED). Reads from FHIR_BASE with an SSRF guard."""
import httpx
from fastapi import APIRouter, Depends, HTTPException

from .. import config
from .. import database as db
from .. import security as sec
from ..schemas import FhirImportIn
from ..services import evidence
from ..services.audit import audit, claim_event
from ..services.net import UnsafeURL, assert_public_http_url
from .claims import get_own

router = APIRouter(prefix="/api/fhir", tags=["fhir"])
HDR = {"Accept": "application/fhir+json"}


def _need_enabled() -> None:
    if not config.FHIR_ENABLED:
        raise HTTPException(501, "FHIR import is turned off. Set FHIR_ENABLED=true (and FHIR_BASE) to use it.")
    try:
        assert_public_http_url(config.FHIR_BASE)
    except UnsafeURL as e:
        raise HTTPException(500, f"FHIR_BASE rejected by the SSRF guard: {e}")


def _get(path: str, params: dict) -> dict:
    try:
        r = httpx.get(f"{config.FHIR_BASE}/{path}", params=params, headers=HDR, timeout=15, follow_redirects=False)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        raise HTTPException(502, "The FHIR server could not be reached or returned an error.")


@router.get("/status")
def status():
    return {"enabled": config.FHIR_ENABLED, "base": config.FHIR_BASE if config.FHIR_ENABLED else None}


@router.get("/patients")
def patients(name: str, user: dict = Depends(sec.current_user)):
    _need_enabled()
    if len(name.strip()) < 2:
        raise HTTPException(422, "Type at least 2 characters.")
    bundle = _get("Patient", {"name": name.strip(), "_count": 10})
    out = []
    for e in bundle.get("entry", []):
        p = e.get("resource", {})
        n = (p.get("name") or [{}])[0]
        out.append({"id": p.get("id"), "name": " ".join(n.get("given", []) + [n.get("family", "")]).strip() or "(no name)", "birthDate": p.get("birthDate"), "gender": p.get("gender")})
    return {"patients": out}


def _txt(cc: dict | None) -> str:
    cc = cc or {}
    return cc.get("text") or ((cc.get("coding") or [{}])[0].get("display")) or ""


@router.post("/claims/{claim_id}/import")
def import_notes(claim_id: int, body: FhirImportIn, user: dict = Depends(sec.current_user)):
    _need_enabled()
    c = get_own(claim_id, user)
    lines = ["Imported from FHIR (R4):"]
    for e in _get("Condition", {"patient": body.patient_id, "_count": 20}).get("entry", []):
        r = e["resource"]
        lines.append(f"Condition: {_txt(r.get('code'))} {r.get('onsetDateTime', '')}".strip() + ".")
    for e in _get("Observation", {"patient": body.patient_id, "_count": 30}).get("entry", []):
        r = e["resource"]
        q = r.get("valueQuantity") or {}
        val = f"{q.get('value')} {q.get('unit', '')}".strip() if q else _txt({"text": r.get("valueString")})
        lines.append(f"Observation: {_txt(r.get('code'))} {val} {r.get('effectiveDateTime', '')}".strip() + ".")
    for e in _get("Procedure", {"patient": body.patient_id, "_count": 20}).get("entry", []):
        r = e["resource"]
        lines.append(f"Procedure: {_txt(r.get('code'))} {r.get('performedDateTime', '')}".strip() + ".")
    if len(lines) == 1:
        raise HTTPException(404, "No clinical data found for that patient on the FHIR server.")
    text = "\n".join(lines)
    merged = (c["ehr_notes"] + "\n\n" + text).strip() if c["ehr_notes"] else text
    db.ex("UPDATE claims SET ehr_notes=?, diagnosis=? WHERE id=?", (merged[:60000], c["diagnosis"] or ", ".join(evidence.extract_icd(merged)), claim_id))
    claim_event(claim_id, "notes_added", f"FHIR import ({len(lines) - 1} items)")
    audit(user["id"], "fhir_import", f"claim {claim_id}")
    return {"imported": len(lines) - 1}
