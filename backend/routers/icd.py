"""ICD-10-CM lookup via the NLM Clinical Tables API, with a 24-hour database cache."""
import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from .. import security as sec

router = APIRouter(prefix="/api/icd", tags=["icd"], dependencies=[Depends(sec.rate_limit("icd", 60))])
NLM = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
TTL = 24 * 3600


@router.get("/search")
def search(q: str = ""):
    q = q.strip()
    if len(q) < 2 or len(q) > 60:
        raise HTTPException(422, "Type 2 to 60 characters.")
    key = q.lower()
    row = db.q1("SELECT payload, ts FROM icd_cache WHERE q=?", (key,))
    if row and time.time() - row["ts"] < TTL:
        return {"results": json.loads(row["payload"]), "cached": True}
    try:
        r = httpx.get(NLM, params={"sf": "code,name", "terms": q, "maxList": 10}, timeout=8)
        r.raise_for_status()
        results = [{"code": c, "name": n} for c, n in r.json()[3]]
    except (httpx.HTTPError, ValueError, IndexError):
        if row:
            return {"results": json.loads(row["payload"]), "cached": True, "stale": True}
        raise HTTPException(503, "ICD-10 lookup is temporarily unavailable. You can type the code manually.")
    db.ex("DELETE FROM icd_cache WHERE q=?", (key,))
    db.ex("INSERT INTO icd_cache(q,payload,ts) VALUES(?,?,?)", (key, json.dumps(results), time.time()))
    return {"results": results, "cached": False}
