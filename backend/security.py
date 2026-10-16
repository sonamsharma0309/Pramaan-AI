"""Passwords, JWT access tokens, rotating refresh tokens, CSRF, role guards and rate limiting.

Session model: short-lived access JWT (15 min) + rotating refresh token (7 d) in httpOnly cookies,
with a double-submit CSRF token. Replaying an already-used refresh token revokes every session of that user.
"""
import hashlib
import hmac
import re
import secrets
import time
import uuid
from collections import defaultdict, deque

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status

from . import config
from . import database as db
from .services.audit import audit

ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE = "pr_at", "pr_rt", "pr_csrf"
SAFE = {"GET", "HEAD", "OPTIONS"}
COMMON = {"password", "password1", "12345678", "123456789", "qwerty123", "iloveyou1", "admin123", "welcome1", "letmein1", "pramaan123"}
_DUMMY = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt(rounds=12))


# ---------------- passwords ----------------
def validate_password(pw: str, email: str = "") -> list[str]:
    errs = []
    if len(pw) < 8:
        errs.append("at least 8 characters")
    if len(pw.encode()) > 72:
        errs.append("at most 72 bytes")
    if not re.search(r"[A-Za-z]", pw):
        errs.append("one letter")
    if not re.search(r"\d", pw):
        errs.append("one number")
    if pw.lower() in COMMON:
        errs.append("not a commonly used password")
    local = email.split("@")[0].lower() if email else ""
    if local and len(local) >= 4 and local in pw.lower():
        errs.append("must not contain your email name")
    return errs


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        if not hashed:
            bcrypt.checkpw(pw.encode()[:72], _DUMMY)  # keeps timing similar for unknown users
            return False
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


# ---------------- tokens ----------------
def create_token(user_id: int, minutes: int | None = None, purpose: str = "access", extra: dict | None = None) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + (minutes or config.ACCESS_TOKEN_MINUTES) * 60, "jti": uuid.uuid4().hex, "pur": purpose}
    payload.update(extra or {})
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_token(token: str, purpose: str = "access") -> dict:
    try:
        data = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token.")
    if data.get("pur") != purpose:
        raise HTTPException(401, "Invalid token.")
    return data


def _hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def public_user(u: dict) -> dict:
    keys = ("id", "name", "email", "org", "org_id", "role", "auth_provider", "created_at", "last_login", "email_verified", "totp_enabled", "theme")
    out = {k: u.get(k) for k in keys}
    out["totp_enabled"] = bool(out["totp_enabled"])
    out["email_verified"] = bool(out["email_verified"])
    return out


def _cookie(resp: Response, name: str, value: str, max_age: int, http_only: bool, path: str = "/") -> None:
    resp.set_cookie(name, value, max_age=max_age, httponly=http_only, samesite="lax", secure=config.COOKIE_SECURE, path=path)


def start_session(resp: Response, user: dict, family: str | None = None) -> None:
    """Issue access + refresh + CSRF cookies. Refresh token is stored hashed, one row per rotation."""
    refresh = secrets.token_urlsafe(48)
    db.ex("INSERT INTO refresh_tokens(user_id,family,token_hash,expires) VALUES(?,?,?,?)",
          (user["id"], family or uuid.uuid4().hex[:24], _hash(refresh), time.time() + config.REFRESH_TOKEN_DAYS * 86400))
    _cookie(resp, ACCESS_COOKIE, create_token(user["id"]), config.ACCESS_TOKEN_MINUTES * 60, True)
    _cookie(resp, REFRESH_COOKIE, refresh, config.REFRESH_TOKEN_DAYS * 86400, True, "/api/auth")
    _cookie(resp, CSRF_COOKIE, secrets.token_urlsafe(24), config.REFRESH_TOKEN_DAYS * 86400, False)


def clear_session(resp: Response) -> None:
    for n, p in ((ACCESS_COOKIE, "/"), (REFRESH_COOKIE, "/api/auth"), (CSRF_COOKIE, "/")):
        resp.delete_cookie(n, path=p)


def revoke_all_sessions(user_id: int) -> None:
    db.ex("UPDATE refresh_tokens SET revoked=1 WHERE user_id=?", (user_id,))


def check_csrf(request: Request) -> None:
    sent, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get(CSRF_COOKIE, "")
    if not sent or not cookie or not hmac.compare_digest(sent, cookie):
        raise HTTPException(403, "CSRF token missing or invalid. Refresh the page and try again.")


def rotate_refresh(request: Request, resp: Response) -> dict:
    """Validate + rotate the refresh cookie. A reused (already rotated) token revokes all sessions."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(401, "No session.")
    row = db.q1("SELECT * FROM refresh_tokens WHERE token_hash=?", (_hash(raw),))
    if not row:
        raise HTTPException(401, "Invalid session.")
    if row["revoked"]:
        revoke_all_sessions(row["user_id"])
        audit(row["user_id"], "refresh_replay", "reused refresh token; all sessions revoked")
        clear_session(resp)
        raise HTTPException(401, "Session invalidated for security. Please sign in again.")
    if row["expires"] < time.time():
        raise HTTPException(401, "Session expired. Please sign in again.")
    db.ex("UPDATE refresh_tokens SET revoked=1 WHERE id=?", (row["id"],))
    user = db.q1("SELECT * FROM users WHERE id=?", (row["user_id"],))
    if not user:
        raise HTTPException(401, "Account not found.")
    start_session(resp, user, row["family"])
    return user


# ---------------- request guards ----------------
def current_user(request: Request) -> dict:
    token, via_cookie = None, False
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif request.cookies.get(ACCESS_COOKIE):
        token, via_cookie = request.cookies[ACCESS_COOKIE], True
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    if via_cookie and request.method not in SAFE:
        sent, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get(CSRF_COOKIE, "")
        if not sent or not cookie or not hmac.compare_digest(sent, cookie):
            raise HTTPException(403, "CSRF token missing or invalid. Refresh the page and try again.")
    data = decode_token(token)
    if db.q1("SELECT 1 AS x FROM revoked_tokens WHERE jti=?", (data["jti"],)):
        raise HTTPException(401, "Session ended. Please sign in again.")
    user = db.q1("SELECT * FROM users WHERE id=?", (int(data["sub"]),))
    if not user:
        raise HTTPException(401, "Account not found.")
    user["_jti"], user["_exp"] = data["jti"], data["exp"]
    return user


def require_role(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "You do not have access to this feature.")
        return user
    return dep


require_biller = require_role("biller")
require_admin = require_role("admin")


# ---------------- rate limiting ----------------
_hits: dict[str, deque] = defaultdict(deque)


def hit(key: str, limit: int, window: int = 60) -> bool:
    """Sliding-window counter. Returns False when the limit is exceeded."""
    now = time.time()
    dq = _hits[key]
    while dq and dq[0] < now - window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def rate_limit(bucket: str, limit: int | None = None, window: int = 60):
    def dep(request: Request):
        lim = config.RATE_AUTH_PER_MIN if limit is None else limit
        if not hit(f"{bucket}:{request.client.host if request.client else 'x'}", lim, window):
            raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")
    return dep


def reset_rate_limits() -> None:
    _hits.clear()
