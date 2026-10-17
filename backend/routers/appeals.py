"""Appeals: view, autosave, regenerate, track outcome, watermarked PDF packet."""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import database as db
from .. import security as sec
from ..schemas import AppealPatch
from ..services import appeal_gen, pipeline
from ..services.audit import audit, claim_event

router = APIRouter(prefix="/api/appeals", tags=["appeals"])
STATUS = {"drafted", "submitted", "won", "partial", "lost"}
CLAIM_STATUS = {"drafted": "appeal_ready", "submitted": "appealed", "won": "recovered", "partial": "recovered", "lost": "lost"}
OUTCOME = {"won": "won", "partial": "partial", "lost": "lost"}
LABEL = {"drafted": "drafted", "submitted": "submitted to the payer", "won": "won", "partial": "partly won", "lost": "lost"}


def own(aid: int, user: dict) -> dict:
    a = db.q1("SELECT * FROM appeals WHERE id=? AND user_id=?", (aid, user["id"]))
    if not a:
        raise HTTPException(404, "Appeal not found.")
    return a


def shape(a: dict) -> dict:
    a = dict(a)
    a["analysis"] = json.loads(a["analysis"] or "{}")
    a["packet_id"] = appeal_gen.packet_id(a)
    return a


@router.get("")
def list_appeals(user: dict = Depends(sec.current_user)):
    rows = db.q("""SELECT a.id,a.claim_id,a.status,a.win_probability,a.model_kind,a.engine,a.gen_seconds,a.created_at,a.recovered_amount,a.outcome,
                   c.claim_no,c.patient_name,c.payer,c.denial_code,c.denied_amount,c.procedure_desc
                   FROM appeals a JOIN claims c ON c.id=a.claim_id WHERE a.user_id=? ORDER BY a.id DESC""", (user["id"],))
    return {"appeals": rows}


@router.get("/{aid}")
def get_appeal(aid: int, user: dict = Depends(sec.current_user)):
    a = shape(own(aid, user))
    a["claim"] = db.q1("SELECT * FROM claims WHERE id=?", (a["claim_id"],))
    a["claim"].pop("ehr_notes", None)
    audit(user["id"], "appeal_viewed", str(aid))
    return {"appeal": a}


@router.patch("/{aid}")
def patch_appeal(aid: int, body: AppealPatch, user: dict = Depends(sec.current_user)):
    a = own(aid, user)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in data and data["status"] not in STATUS:
        raise HTTPException(422, "Unknown status.")
    claim = db.q1("SELECT * FROM claims WHERE id=?", (a["claim_id"],))
    new_status = data.get("status", a["status"])
    if new_status == "won" and "recovered_amount" not in data and not a["recovered_amount"]:
        data["recovered_amount"] = claim["denied_amount"] or claim["billed_amount"]
    if "status" in data:
        data["outcome"] = OUTCOME.get(new_status)
        if new_status in ("drafted", "submitted", "lost"):
            data["recovered_amount"] = 0
    if data:
        db.ex(f"UPDATE appeals SET {', '.join(k + '=?' for k in data)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*data.values(), aid))
    if "status" in data and data["status"] != a["status"]:
        db.ex("UPDATE claims SET status=? WHERE id=?", (CLAIM_STATUS[new_status], a["claim_id"]))
        claim_event(a["claim_id"], f"appeal_{new_status}", f"recovered {data.get('recovered_amount', 0)}" if new_status in ("won", "partial") else "")
        db.ex("INSERT INTO notifications(user_id,kind,ref,title,body,link) VALUES(?,?,?,?,?,?)",
              (user["id"], "status", f"appeal:{aid}:{new_status}", f"Appeal {LABEL[new_status]}", f"Claim {claim['claim_no']} for {claim['patient_name']} is now {LABEL[new_status]}.",
               f"#/{'b' if user['role'] == 'biller' else 'p'}/appeal/{aid}"))
        audit(user["id"], "appeal_status", f"{aid} -> {new_status}")
    return {"appeal": shape(own(aid, user))}


@router.post("/{aid}/regenerate")
def regenerate(aid: int, user: dict = Depends(sec.current_user)):
    """Re-run analysis on the latest claim data and rewrite the letter (uses Claude when configured)."""
    a = own(aid, user)
    claim = db.q1("SELECT * FROM claims WHERE id=?", (a["claim_id"],))
    an = pipeline.analyze(claim, user)
    letter, engine = appeal_gen.generate(claim, an, user)
    db.ex("UPDATE appeals SET letter=?, analysis=?, win_probability=?, model_kind=?, engine=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
          (letter, json.dumps(an), an["prediction"]["probability"], an["prediction"]["model_kind"], engine, aid))
    claim_event(a["claim_id"], "appeal_regenerated", f"engine {engine}")
    audit(user["id"], "appeal_regenerated", str(aid))
    return {"appeal": shape(own(aid, user))}


@router.delete("/{aid}")
def delete_appeal(aid: int, user: dict = Depends(sec.current_user)):
    a = own(aid, user)
    db.ex("DELETE FROM appeals WHERE id=?", (aid,))
    db.ex("UPDATE claims SET status='denied' WHERE id=? AND status='appeal_ready'", (a["claim_id"],))
    return {"ok": True}


def pdf_bytes(a: dict) -> tuple[bytes, dict]:
    a = shape(a)
    claim = db.q1("SELECT * FROM claims WHERE id=?", (a["claim_id"],))
    return appeal_gen.build_pdf(claim, a, a["analysis"]), claim


@router.get("/{aid}/pdf")
def pdf(aid: int, user: dict = Depends(sec.current_user)):
    data, claim = pdf_bytes(own(aid, user))
    audit(user["id"], "appeal_pdf", str(aid))
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="appeal-{claim["claim_no"]}.pdf"'})
