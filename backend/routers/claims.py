"""Claims: CRUD, 835 import, chart notes, analysis, appeal generation, bulk actions, timeline."""
import json
import math
import time

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from .. import database as db
from .. import security as sec
from ..data import demo
from ..schemas import BulkIn, ClaimIn, ClaimPatch
from ..services import appeal_gen, deadlines, denial_codes, edi835, evidence, pipeline
from ..services.audit import audit, claim_event
from ..services.files import read_text

router = APIRouter(prefix="/api/claims", tags=["claims"])
STATUSES = {"denied", "appeal_ready", "appealed", "recovered", "lost", "written_off"}
SORTS = {"id": "c.id", "claim_no": "c.claim_no", "patient_name": "c.patient_name", "payer": "c.payer", "amount": "c.denied_amount",
         "denied_on": "c.denied_on", "status": "c.status", "deadline": "c.denied_on", "win": "win_probability"}
require_biller = sec.require_biller


def get_own(claim_id: int, user: dict) -> dict:
    c = db.q1("SELECT * FROM claims WHERE id=? AND user_id=?", (claim_id, user["id"]))
    if not c:
        raise HTTPException(404, "Claim not found.")
    return c


def _fill(c: dict) -> dict:
    code = (c.get("denial_code") or "").strip()
    d = denial_codes.info(code) if code else None
    if d:
        c["denial_category"] = d["category"]
        if not c.get("denial_reason"):
            c["denial_reason"] = d["official_description"] or d["description"]
    if not c.get("procedure_desc") and c.get("procedure_code"):
        c["procedure_desc"] = denial_codes.CPT.get(c["procedure_code"], "")
    if not c.get("diagnosis") and c.get("ehr_notes"):
        c["diagnosis"] = ", ".join(evidence.extract_icd(c["ehr_notes"]))
    if not c.get("denied_amount") and c.get("billed_amount"):
        c["denied_amount"] = c["billed_amount"]
    return c


def insert_claim(user_id: int, c: dict, source: str) -> int:
    c = _fill(dict(c))
    cid = db.ex(
        """INSERT INTO claims(user_id,claim_no,patient_name,payer,procedure_code,procedure_desc,diagnosis,billed_amount,denied_amount,
           denial_code,denial_reason,remark_code,denial_category,group_code,service_date,denied_on,ehr_notes,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, c["claim_no"], c["patient_name"], c["payer"], c.get("procedure_code", ""), c.get("procedure_desc", ""), c.get("diagnosis", ""),
         c.get("billed_amount", 0), c.get("denied_amount", 0), c.get("denial_code", ""), c.get("denial_reason", ""), c.get("remark_code", ""),
         c.get("denial_category", ""), c.get("group_code", ""), c.get("service_date", ""), c.get("denied_on", ""), c.get("ehr_notes", ""), source))
    claim_event(cid, "imported" if source != "manual" else "created", f"source: {source}")
    return cid


@router.get("")
def list_claims(status: str = "", q: str = "", payer: str = "", category: str = "", date_from: str = "", date_to: str = "",
                sort: str = "id", order: str = "desc", page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100),
                user: dict = Depends(sec.current_user)):
    where, args = ["c.user_id=?"], [user["id"]]
    if status:
        where.append("c.status=?"); args.append(status)
    if payer:
        where.append("c.payer=?"); args.append(payer)
    if category:
        where.append("c.denial_category=?"); args.append(category)
    if date_from:
        where.append("c.denied_on>=?"); args.append(date_from)
    if date_to:
        where.append("c.denied_on<=?"); args.append(date_to)
    if q:
        where.append("(LOWER(c.patient_name) LIKE ? OR LOWER(c.claim_no) LIKE ? OR LOWER(c.payer) LIKE ? OR LOWER(c.procedure_code) LIKE ?)")
        args += [f"%{q.lower()}%"] * 4
    w = " AND ".join(where)
    total = db.q1(f"SELECT COUNT(*) AS n FROM claims c WHERE {w}", args)["n"]
    col = SORTS.get(sort, "c.id")
    direction = "ASC" if order.lower() == "asc" else "DESC"
    rows = db.q(f"""SELECT c.id,c.claim_no,c.patient_name,c.payer,c.procedure_code,c.procedure_desc,c.denial_code,c.denial_category,c.denied_amount,
                    c.billed_amount,c.denied_on,c.status,c.source,
                    (SELECT id FROM appeals a WHERE a.claim_id=c.id ORDER BY a.id DESC LIMIT 1) AS appeal_id,
                    (SELECT win_probability FROM appeals a WHERE a.claim_id=c.id ORDER BY a.id DESC LIMIT 1) AS win_probability
                    FROM claims c WHERE {w} ORDER BY {col} {direction}, c.id DESC LIMIT ? OFFSET ?""", args + [page_size, (page - 1) * page_size])
    for r in rows:
        r["deadline"] = deadlines.deadline(r["payer"], r["denied_on"])
    return {"claims": rows, "total": total, "page": page, "page_size": page_size, "pages": max(1, math.ceil(total / page_size))}


@router.post("", status_code=201)
def create_claim(body: ClaimIn, user: dict = Depends(sec.current_user)):
    cid = insert_claim(user["id"], body.model_dump(), "patient" if user["role"] == "patient" else "manual")
    return {"claim": get_own(cid, user)}


def import_text(text: str, user: dict) -> dict:
    try:
        parsed = edi835.parse_835(text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    existing = {r["claim_no"] for r in db.q("SELECT claim_no FROM claims WHERE user_id=?", (user["id"],))}
    created, skipped = [], 0
    for c in parsed:
        if c["claim_no"] in existing:
            skipped += 1
            continue
        created.append(insert_claim(user["id"], c, "835"))
    audit(user["id"], "import_835", f"{len(created)} imported")
    return {"imported": len(created), "skipped_duplicates": skipped, "denied_found": len(parsed), "ids": created}


@router.post("/import-835")
async def import_835(file: UploadFile = File(...), user: dict = Depends(require_biller)):
    return import_text(await read_text(file), user)


@router.post("/seed-demo")
def seed_demo(sample: str = "main", user: dict = Depends(sec.current_user)):
    """Load a bundled FICTIONAL sample remittance (and matching demo chart notes) into this account."""
    path = demo.SAMPLES.get(sample)
    if not path:
        raise HTTPException(404, "Unknown sample.")
    res = import_text(path.read_text(), user)
    for cid in res["ids"]:
        c = db.q1("SELECT patient_name FROM claims WHERE id=?", (cid,))
        d = demo.DEMO.get((c["patient_name"].split()[-1] if c["patient_name"] else "").lower())
        if d:
            db.ex("UPDATE claims SET ehr_notes=?, diagnosis=? WHERE id=?", (d["ehr"], d["diagnosis"], cid))
            claim_event(cid, "notes_added", "demo chart (fictional)")
    return res


@router.post("/bulk/analyze")
def bulk_analyze(body: BulkIn, user: dict = Depends(sec.current_user)):
    out = []
    for cid in body.ids:
        c = db.q1("SELECT * FROM claims WHERE id=? AND user_id=?", (cid, user["id"]))
        if not c:
            out.append({"id": cid, "ok": False, "error": "not found"})
            continue
        a = pipeline.analyze(c, user)
        claim_event(cid, "analysed", f"win estimate {round(a['prediction']['probability'] * 100)}%")
        out.append({"id": cid, "ok": True, "claim_no": c["claim_no"], "win": a["prediction"]["probability"], "coverage": a["coverage"], "no_policy": a["no_policy"]})
    return {"results": out}


@router.post("/bulk/appeal")
def bulk_appeal(body: BulkIn, user: dict = Depends(sec.current_user)):
    out = []
    for cid in body.ids:
        try:
            r = make_appeal(cid, user)
            out.append({"id": cid, "ok": True, **r})
        except HTTPException as e:
            out.append({"id": cid, "ok": False, "error": e.detail})
    return {"results": out}


@router.get("/{claim_id}")
def get_claim(claim_id: int, user: dict = Depends(sec.current_user)):
    c = get_own(claim_id, user)
    c["denial"] = denial_codes.info(c["denial_code"])
    c["deadline"] = deadlines.deadline(c["payer"], c["denied_on"])
    c["group"] = deadlines.group_info(c.get("group_code", ""))
    c["appeals"] = db.q("SELECT id,status,win_probability,engine,created_at,outcome,recovered_amount FROM appeals WHERE claim_id=? ORDER BY id DESC", (claim_id,))
    return {"claim": c}


@router.get("/{claim_id}/timeline")
def timeline(claim_id: int, user: dict = Depends(sec.current_user)):
    get_own(claim_id, user)
    return {"events": db.q("SELECT event,detail,created_at FROM claim_events WHERE claim_id=? ORDER BY id", (claim_id,))}


@router.patch("/{claim_id}")
def patch_claim(claim_id: int, body: ClaimPatch, user: dict = Depends(sec.current_user)):
    get_own(claim_id, user)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in data and data["status"] not in STATUSES:
        raise HTTPException(422, "Unknown status.")
    if "denial_code" in data:
        data["denial_category"] = denial_codes.info(data["denial_code"])["category"]
    if data:
        db.ex(f"UPDATE claims SET {', '.join(k + '=?' for k in data)} WHERE id=?", (*data.values(), claim_id))
        claim_event(claim_id, "status_changed" if "status" in data else "edited", ", ".join(data.keys())[:200])
    return {"claim": get_own(claim_id, user)}


@router.delete("/{claim_id}")
def delete_claim(claim_id: int, user: dict = Depends(sec.current_user)):
    get_own(claim_id, user)
    db.ex("DELETE FROM claim_events WHERE claim_id=?", (claim_id,))
    db.ex("DELETE FROM appeals WHERE claim_id=?", (claim_id,))
    db.ex("DELETE FROM claims WHERE id=?", (claim_id,))
    audit(user["id"], "claim_deleted", str(claim_id))
    return {"ok": True}


@router.post("/{claim_id}/notes-file")
async def notes_file(claim_id: int, file: UploadFile = File(...), user: dict = Depends(sec.current_user)):
    c = get_own(claim_id, user)
    text = (await read_text(file)).strip()
    merged = (c["ehr_notes"] + "\n\n" + text).strip() if c["ehr_notes"] else text
    diag = c["diagnosis"] or ", ".join(evidence.extract_icd(merged))
    db.ex("UPDATE claims SET ehr_notes=?, diagnosis=? WHERE id=?", (merged[:60000], diag, claim_id))
    claim_event(claim_id, "notes_added", f"uploaded {file.filename}"[:200])
    return {"claim": get_own(claim_id, user)}


@router.post("/{claim_id}/analyze")
def analyze(claim_id: int, user: dict = Depends(sec.current_user)):
    c = get_own(claim_id, user)
    a = pipeline.analyze(c, user)
    claim_event(claim_id, "analysed", f"win estimate {round(a['prediction']['probability'] * 100)}%")
    return {"analysis": a}


def make_appeal(claim_id: int, user: dict) -> dict:
    t0 = time.perf_counter()
    c = get_own(claim_id, user)
    a = pipeline.analyze(c, user)
    if not a["denial"]["appealable"]:
        raise HTTPException(400, f"{a['denial']['category_label']} adjustments are not normally appealable.")
    letter, engine = appeal_gen.generate(c, a, user)
    secs = round(time.perf_counter() - t0, 2)
    aid = db.ex("INSERT INTO appeals(claim_id,user_id,letter,analysis,win_probability,model_kind,engine,gen_seconds) VALUES(?,?,?,?,?,?,?,?)",
                (claim_id, user["id"], letter, json.dumps(a), a["prediction"]["probability"], a["prediction"]["model_kind"], engine, secs))
    if c["status"] == "denied":
        db.ex("UPDATE claims SET status='appeal_ready' WHERE id=?", (claim_id,))
    claim_event(claim_id, "appeal_generated", f"engine {engine}, {secs}s")
    audit(user["id"], "appeal_generated", f"claim {claim_id}")
    return {"appeal_id": aid, "seconds": secs, "engine": engine}


@router.post("/{claim_id}/appeal", status_code=201)
def appeal(claim_id: int, user: dict = Depends(sec.current_user)):
    return make_appeal(claim_id, user)
