"""Exports: claims/outcomes CSV and a ZIP of every appeal PDF packet."""
import csv
import io
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from .. import database as db
from .. import security as sec
from ..services.audit import audit
from .appeals import pdf_bytes

router = APIRouter(prefix="/api/export", tags=["export"])
_SAFE = ("=", "+", "-", "@", "\t", "\r")


def _cell(v):
    """Neutralise spreadsheet formula injection (CSV injection) in exported text."""
    return "'" + v if isinstance(v, str) and v.startswith(_SAFE) else v


def _csv(rows: list[dict], cols: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([_cell(r.get(c, "")) for c in cols])
    return buf.getvalue().encode("utf-8-sig")


def _csv_resp(data: bytes, name: str) -> Response:
    return Response(data, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/claims.csv")
def claims_csv(user: dict = Depends(sec.current_user)):
    rows = db.q("SELECT * FROM claims WHERE user_id=? ORDER BY id", (user["id"],))
    audit(user["id"], "export_claims", f"{len(rows)} rows")
    cols = ["claim_no", "patient_name", "payer", "procedure_code", "procedure_desc", "denial_code", "denial_category", "billed_amount", "denied_amount", "denied_on", "status"]
    return _csv_resp(_csv(rows, cols), "claims.csv")


@router.get("/outcomes.csv")
def outcomes_csv(user: dict = Depends(sec.current_user)):
    rows = db.q("""SELECT c.claim_no,c.patient_name,c.payer,c.denial_code,c.denied_amount,a.status,a.outcome,a.win_probability,a.model_kind,a.recovered_amount,a.created_at
                   FROM appeals a JOIN claims c ON c.id=a.claim_id WHERE a.user_id=? ORDER BY a.id""", (user["id"],))
    audit(user["id"], "export_outcomes", f"{len(rows)} rows")
    cols = ["claim_no", "patient_name", "payer", "denial_code", "denied_amount", "status", "outcome", "win_probability", "model_kind", "recovered_amount", "created_at"]
    return _csv_resp(_csv(rows, cols), "outcomes.csv")


@router.get("/packets.zip")
def packets_zip(user: dict = Depends(sec.current_user)):
    buf = io.BytesIO()
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for a in db.q("SELECT * FROM appeals WHERE user_id=? ORDER BY id", (user["id"],)):
            data, claim = pdf_bytes(a)
            z.writestr(f"appeal-{claim['claim_no']}-{a['id']}.pdf".replace("/", "_"), data)
            n += 1
    audit(user["id"], "export_packets", f"{n} packets")
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="appeal-packets.zip"'})
