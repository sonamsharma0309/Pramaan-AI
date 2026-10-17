"""Policy library (RAG corpus): a read-only shared library plus each organisation's private uploads."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import database as db
from .. import security as sec
from ..schemas import PolicyIn, SearchIn
from ..services import rag
from ..services.audit import audit
from ..services.files import read_text

router = APIRouter(prefix="/api/policies", tags=["policies"])


def _visible(user: dict) -> list[dict]:
    return db.q("SELECT * FROM policies WHERE org_id IS NULL OR org_id=?", (user.get("org_id"),))


@router.get("")
def list_policies(user: dict = Depends(sec.current_user)):
    rows = db.q("SELECT id,org_id,payer,title,length(content) AS size,created_at FROM policies WHERE org_id IS NULL OR org_id=? ORDER BY payer,title", (user.get("org_id"),))
    for r in rows:
        r["shared"] = r["org_id"] is None
        r["chunks"] = None
    return {"policies": rows}


@router.get("/payers")
def payers(user: dict = Depends(sec.current_user)):
    return {"payers": sorted({p["payer"] for p in _visible(user) if p["payer"].upper() not in ("ALL", "GENERAL")})}


@router.get("/{pid}")
def get_policy(pid: int, user: dict = Depends(sec.current_user)):
    p = db.q1("SELECT * FROM policies WHERE id=? AND (org_id IS NULL OR org_id=?)", (pid, user.get("org_id")))
    if not p:
        raise HTTPException(404, "Policy not found.")
    return {"policy": p}


@router.post("", status_code=201)
def add_policy(body: PolicyIn, user: dict = Depends(sec.require_biller)):
    pid = db.ex("INSERT INTO policies(user_id,org_id,payer,title,content) VALUES(?,?,?,?,?)", (user["id"], user["org_id"], body.payer.strip(), body.title.strip(), body.content.strip()))
    audit(user["id"], "policy_added", str(pid))
    return {"id": pid}


@router.post("/upload", status_code=201)
async def upload_policy(payer: str = Form(...), title: str = Form(""), file: UploadFile = File(...), user: dict = Depends(sec.require_biller)):
    text = (await read_text(file)).strip()
    if len(text) < 50:
        raise HTTPException(400, "The file has too little text to index.")
    pid = db.ex("INSERT INTO policies(user_id,org_id,payer,title,content) VALUES(?,?,?,?,?)",
                (user["id"], user["org_id"], payer.strip(), (title or file.filename or "Uploaded policy").strip()[:160], text[:200000]))
    audit(user["id"], "policy_uploaded", f"{pid} {file.filename}")
    return {"id": pid, "chunks": len(rag.chunk_text(text))}


@router.delete("/{pid}")
def delete_policy(pid: int, user: dict = Depends(sec.require_biller)):
    if not db.q1("SELECT 1 AS x FROM policies WHERE id=? AND org_id=?", (pid, user["org_id"])):
        raise HTTPException(404, "Policy not found, or it is a shared policy you cannot delete.")
    db.ex("DELETE FROM policies WHERE id=?", (pid,))
    audit(user["id"], "policy_deleted", str(pid))
    return {"ok": True}


@router.post("/search")
def search(body: SearchIn, user: dict = Depends(sec.current_user)):
    pols = _visible(user)
    if body.payer:
        pols = [p for p in pols if rag.payer_matches(p["payer"], body.payer)]
    return {"hits": rag.retrieve(body.query, pols, k=5)}
