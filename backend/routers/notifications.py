"""In-app notifications: appeal deadline reminders (generated on demand, de-duplicated) and status changes."""
from fastapi import APIRouter, Depends

from .. import database as db
from .. import security as sec
from ..services import deadlines

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _sync_deadlines(user: dict) -> None:
    rows = db.q("SELECT id,claim_no,patient_name,payer,denied_on FROM claims WHERE user_id=? AND status IN ('denied','appeal_ready')", (user["id"],))
    base = "#/b" if user["role"] == "biller" else "#/p"
    for c in rows:
        left = deadlines.deadline(c["payer"], c["denied_on"])["days_left"]
        if left is None or left > 30:
            continue
        bucket = "expired" if left <= 0 else "7" if left <= 7 else "30"
        ref = f"deadline:{c['id']}:{bucket}"
        if not db.q1("SELECT 1 AS x FROM notifications WHERE user_id=? AND ref=?", (user["id"], ref)):
            title = "Appeal window has passed" if left <= 0 else f"{left} days left to appeal"
            db.ex("INSERT INTO notifications(user_id,kind,ref,title,body,link) VALUES(?,?,?,?,?,?)",
                  (user["id"], "deadline", ref, title, f"Claim {c['claim_no']} for {c['patient_name']} has no submitted appeal yet.", f"{base}/claim/{c['id']}"))


@router.get("")
def list_notifications(user: dict = Depends(sec.current_user)):
    _sync_deadlines(user)
    rows = db.q("SELECT id,kind,title,body,link,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30", (user["id"],))
    return {"notifications": rows, "unread": sum(1 for r in rows if not r["is_read"])}


@router.post("/read-all")
def read_all(user: dict = Depends(sec.current_user)):
    db.ex("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}
