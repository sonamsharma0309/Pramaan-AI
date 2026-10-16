"""Request context (request id / client ip) and the audit log writer."""
import contextvars

from .. import database as db

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
client_ip: contextvars.ContextVar[str] = contextvars.ContextVar("client_ip", default="-")


def audit(user_id: int | None, action: str, detail: str = "") -> None:
    """Append an audit entry. Never raises: auditing must not break a request."""
    try:
        db.ex("INSERT INTO audit_log(user_id,action,detail,ip,request_id) VALUES(?,?,?,?,?)",
              (user_id, action, detail[:400], client_ip.get(), request_id.get()))
    except Exception:  # pragma: no cover
        pass


def claim_event(claim_id: int, event: str, detail: str = "") -> None:
    db.ex("INSERT INTO claim_events(claim_id,event,detail) VALUES(?,?,?)", (claim_id, event, detail[:300]))
