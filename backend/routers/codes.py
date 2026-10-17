"""Denial-code lookup backed by the CARC/RARC/EOB dataset."""
from fastapi import APIRouter, Depends, HTTPException

from .. import security as sec
from ..services import denial_codes as dc

router = APIRouter(prefix="/api/codes", tags=["codes"], dependencies=[Depends(sec.rate_limit("codes", 60, 60))])


@router.get("/stats")
def stats():
    return {"source": dc.DATASET_SOURCE, "carc": len(dc.CARC_DESC), "rarc": len(dc.RARC_DESC), "eob": len(dc.EOB)}


@router.get("/list")
def autocomplete(q: str = "", limit: int = 10, appealable: bool = False):
    """Autocomplete for the appeal wizard: matching CARC codes (curated common codes when q is empty)."""
    limit = max(1, min(limit, 25))
    if not q.strip():
        items = [{"code": k, "description": dc.info(k)["official_description"], "category": dc.info(k)["category"]} for k in dc.CARC]
    else:
        items = [{"code": c["code"], "description": c["description"], "category": dc.info(c["code"])["category"]} for c in dc.search(q, 60)["carc"]]
    if appealable:
        items = [i for i in items if dc.info(i["code"])["appealable"]]
    return {"codes": items[:limit]}


@router.get("/categories")
def categories():
    return {"categories": [{"key": k, "label": v} for k, v in dc.CATEGORY_LABEL.items()]}


@router.get("/search")
def search(q: str = ""):
    if len(q.strip()) < 1 or len(q) > 80:
        raise HTTPException(422, "Enter 1 to 80 characters.")
    return dc.search(q)


@router.get("/carc/{code}")
def carc(code: str):
    i = dc.info(code)
    if not i["in_dataset"] and code.strip() not in dc.CARC:
        raise HTTPException(404, "Code not found in the dataset.")
    related = [e for e in dc.EOB.values() if e["carc"] == i["code"]][:25]
    return {"carc": i, "related_eob": [{**e, "rarc_desc": dc.RARC_DESC.get(e["rarc"], "")} for e in related]}
