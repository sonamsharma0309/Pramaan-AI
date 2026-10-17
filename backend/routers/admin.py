"""Admin console API. Admin accounts are created only with scripts/create_admin.py, never through sign-up."""
from fastapi import APIRouter, Depends, HTTPException, Query

from .. import database as db
from .. import security as sec
from ..services.audit import audit
from .misc import health

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(sec.require_admin)])


@router.get("/overview")
def overview():
    n = lambda t: db.q1(f"SELECT COUNT(*) AS n FROM {t}")["n"]  # noqa: E731
    return {"users": n("users"), "claims": n("claims"), "appeals": n("appeals"), "messages": n("contact_messages"), "audit_events": n("audit_log"),
            "by_role": {r["role"]: r["n"] for r in db.q("SELECT role, COUNT(*) AS n FROM users GROUP BY role")}}


@router.get("/users")
def users():
    return {"users": db.q("SELECT id,name,email,role,org,auth_provider,email_verified,totp_enabled,created_at,last_login FROM users ORDER BY id DESC LIMIT 500")}


@router.delete("/users/{uid}")
def delete_user(uid: int, admin: dict = Depends(sec.require_admin)):
    u = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        raise HTTPException(404, "User not found.")
    if u["role"] == "admin":
        raise HTTPException(400, "Admin accounts cannot be deleted here.")
    for c in db.q("SELECT id FROM claims WHERE user_id=?", (uid,)):
        db.ex("DELETE FROM claim_events WHERE claim_id=?", (c["id"],))
        db.ex("DELETE FROM appeals WHERE claim_id=?", (c["id"],))
    db.ex("DELETE FROM claims WHERE user_id=?", (uid,))
    db.ex("DELETE FROM refresh_tokens WHERE user_id=?", (uid,))
    db.ex("DELETE FROM notifications WHERE user_id=?", (uid,))
    db.ex("DELETE FROM users WHERE id=?", (uid,))
    audit(admin["id"], "admin_user_deleted", u["email"])
    return {"ok": True}


@router.get("/messages")
def messages():
    return {"messages": db.q("SELECT * FROM contact_messages ORDER BY id DESC LIMIT 200")}


@router.get("/audit")
def audit_log(action: str = "", limit: int = Query(100, ge=1, le=500)):
    where, args = ("WHERE action=?", [action]) if action else ("", [])
    rows = db.q(f"SELECT a.*, u.email FROM audit_log a LEFT JOIN users u ON u.id=a.user_id {where} ORDER BY a.id DESC LIMIT ?", args + [limit])
    return {"events": rows}


@router.get("/system")
def system():
    return health()
