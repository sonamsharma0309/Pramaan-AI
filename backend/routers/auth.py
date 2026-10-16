"""Authentication: register/login per portal, cookie sessions with rotating refresh, 2FA, verification, reset, Google."""
import secrets
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .. import config
from .. import database as db
from .. import security as sec
from ..schemas import ChangePasswordIn, ForgotIn, GoogleIn, LoginIn, ProfileIn, RegisterIn, ResetIn, ThemeIn, TokenIn, TotpIn
from ..services import totp
from ..services.audit import audit
from ..services.mail import mail_enabled, send_mail

router = APIRouter(prefix="/api/auth", tags=["auth"])
PORTAL_NAME = {"patient": "Patient Portal", "biller": "Billing Portal", "admin": "Admin Console"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_portal(user: dict, portal: str | None) -> None:
    if portal and user["role"] != portal:
        raise HTTPException(403, f"This account belongs to the {PORTAL_NAME[user['role']]}. Please use that portal to sign in.")


def _login_ok(resp: Response, user: dict, how: str) -> dict:
    if config.REQUIRE_VERIFIED and not user["email_verified"]:
        raise HTTPException(403, "Please verify your email first. Check your inbox for the link.")
    db.ex("UPDATE users SET failed_attempts=0, locked_until=0, last_login=? WHERE id=?", (_now(), user["id"]))
    sec.start_session(resp, user)
    audit(user["id"], "login", how)
    return {"user": sec.public_user(db.q1("SELECT * FROM users WHERE id=?", (user["id"],)))}


def _verify_link(user: dict) -> str:
    return f"{config.APP_URL}/#/verify?token={sec.create_token(user['id'], 60 * 24, 'verify')}"


def _send_verification(user: dict) -> str | None:
    link = _verify_link(user)
    sent = send_mail(user["email"], "Verify your Pramaan AI email", f"Welcome to Pramaan AI. Verify your email (valid 24 hours):\n\n{link}\n")
    return link if (not sent and config.DEV_MODE) else None


@router.post("/register", dependencies=[Depends(sec.rate_limit("register"))])
def register(body: RegisterIn, resp: Response):
    email = body.email.lower()
    errs = sec.validate_password(body.password, email)
    if errs:
        raise HTTPException(422, "Password needs: " + ", ".join(errs) + ".")
    if body.role == "biller" and not (body.org or body.invite_code):
        raise HTTPException(422, "Enter your practice or billing company name, or an invite code from your team.")
    if db.q1("SELECT 1 AS x FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    org_id, org_name = None, body.org
    if body.role == "biller":
        if body.invite_code:
            o = db.q1("SELECT * FROM orgs WHERE invite_code=?", (body.invite_code.strip().upper(),))
            if not o:
                raise HTTPException(422, "That invite code is not valid.")
            org_id, org_name = o["id"], o["name"]
        else:
            org_id = db.ex("INSERT INTO orgs(name,invite_code) VALUES(?,?)", (body.org, secrets.token_hex(4).upper()))
    verified = 0 if config.REQUIRE_VERIFIED else 1
    uid = db.ex("INSERT INTO users(name,email,password_hash,org,org_id,role,email_verified) VALUES(?,?,?,?,?,?,?)",
                (body.name, email, sec.hash_password(body.password), org_name, org_id, body.role, verified))
    user = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    audit(uid, "register", body.role)
    if config.REQUIRE_VERIFIED:
        dev = _send_verification(user)
        return {"user": sec.public_user(user), "verification_required": True, "dev_verify_link": dev}
    sec.start_session(resp, user)
    return {"user": sec.public_user(user)}


@router.post("/login", dependencies=[Depends(sec.rate_limit("login"))])
def login(body: LoginIn, resp: Response):
    email = body.email.lower()
    user = db.q1("SELECT * FROM users WHERE email=?", (email,))
    now = time.time()
    if user and user["locked_until"] and user["locked_until"] > now:
        mins = int((user["locked_until"] - now) // 60) + 1
        raise HTTPException(423, f"Too many failed attempts. Try again in {mins} minute(s) or reset your password.")
    if not user or not sec.verify_password(body.password, user["password_hash"] if user else None):
        if user:
            n = (user["failed_attempts"] or 0) + 1
            lock = now + config.LOGIN_LOCK_SECONDS if n >= config.LOGIN_MAX_ATTEMPTS else 0
            db.ex("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?", (0 if lock else n, lock, user["id"]))
            audit(user["id"], "login_failed", f"attempt {n}")
        raise HTTPException(401, "Incorrect email or password.")
    _check_portal(user, body.portal)
    if user["totp_enabled"]:
        if not body.totp_code:
            return JSONResponse({"detail": "Enter the 6-digit code from your authenticator app.", "need_2fa": True}, status_code=401)
        if not totp.verify(user["totp_secret"], body.totp_code):
            audit(user["id"], "login_failed", "bad 2fa code")
            raise HTTPException(401, "That authenticator code is not correct.")
    return _login_ok(resp, user, "password")


@router.get("/google-config")
def google_config():
    return {"enabled": bool(config.GOOGLE_CLIENT_ID), "client_id": config.GOOGLE_CLIENT_ID}


@router.post("/google", dependencies=[Depends(sec.rate_limit("google"))])
def google_login(body: GoogleIn, resp: Response):
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google sign-in is not configured on this server.")
    try:
        r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": body.credential}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach Google. Try again.")
    info = r.json() if r.status_code == 200 else {}
    if info.get("aud") != config.GOOGLE_CLIENT_ID or str(info.get("email_verified")).lower() != "true":
        raise HTTPException(401, "Google sign-in failed.")
    email = info["email"].lower()
    user = db.q1("SELECT * FROM users WHERE email=?", (email,))
    if not user:
        org_id = None
        if body.role == "biller":
            org_id = db.ex("INSERT INTO orgs(name,invite_code) VALUES(?,?)", (f"{info.get('name') or email}'s practice", secrets.token_hex(4).upper()))
        uid = db.ex("INSERT INTO users(name,email,role,auth_provider,org_id,org,email_verified) VALUES(?,?,?,'google',?,?,1)",
                    (info.get("name") or email.split("@")[0], email, body.role, org_id, ""))
        user = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    _check_portal(user, body.portal)
    return _login_ok(resp, user, "google")


@router.post("/refresh")
def refresh(request: Request, resp: Response):
    sec.check_csrf(request)
    user = sec.rotate_refresh(request, resp)
    return {"user": sec.public_user(user)}


@router.post("/logout")
def logout(request: Request, resp: Response, user: dict = Depends(sec.current_user)):
    db.ex("INSERT OR IGNORE INTO revoked_tokens(jti,exp) VALUES(?,?)", (user["_jti"], user["_exp"]))
    raw = request.cookies.get(sec.REFRESH_COOKIE)
    if raw:
        db.ex("UPDATE refresh_tokens SET revoked=1 WHERE token_hash=?", (sec._hash(raw),))
    db.ex("DELETE FROM revoked_tokens WHERE exp < ?", (time.time(),))
    sec.clear_session(resp)
    audit(user["id"], "logout")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(sec.current_user)):
    return {"user": sec.public_user(user)}


@router.patch("/me")
def update_me(body: ProfileIn, user: dict = Depends(sec.current_user)):
    name = body.name.strip() if body.name else user["name"]
    db.ex("UPDATE users SET name=? WHERE id=?", (name, user["id"]))
    return {"user": sec.public_user(db.q1("SELECT * FROM users WHERE id=?", (user["id"],)))}


@router.put("/theme")
def set_theme(body: ThemeIn, user: dict = Depends(sec.current_user)):
    db.ex("UPDATE users SET theme=? WHERE id=?", (body.theme, user["id"]))
    return {"theme": body.theme}


@router.get("/org")
def org(user: dict = Depends(sec.require_biller)):
    o = db.q1("SELECT * FROM orgs WHERE id=?", (user["org_id"],))
    members = db.q("SELECT name,email,last_login FROM users WHERE org_id=? ORDER BY id", (user["org_id"],)) if o else []
    return {"org": o, "members": members}


@router.post("/change-password", dependencies=[Depends(sec.rate_limit("chpw"))])
def change_password(body: ChangePasswordIn, resp: Response, user: dict = Depends(sec.current_user)):
    if not user["password_hash"]:
        raise HTTPException(400, "This account signs in with Google and has no password. Use 'Forgot password' to set one.")
    if not sec.verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect.")
    errs = sec.validate_password(body.new_password, user["email"])
    if errs:
        raise HTTPException(422, "Password needs: " + ", ".join(errs) + ".")
    db.ex("UPDATE users SET password_hash=? WHERE id=?", (sec.hash_password(body.new_password), user["id"]))
    db.ex("INSERT OR IGNORE INTO revoked_tokens(jti,exp) VALUES(?,?)", (user["_jti"], user["_exp"]))
    sec.revoke_all_sessions(user["id"])
    sec.start_session(resp, user)
    audit(user["id"], "password_changed")
    return {"user": sec.public_user(user)}


@router.post("/forgot", dependencies=[Depends(sec.rate_limit("forgot", 5))])
def forgot(body: ForgotIn):
    resp = {"message": "If that email is registered, a reset link has been sent.", "mail_configured": mail_enabled()}
    user = db.q1("SELECT * FROM users WHERE email=?", (body.email.lower(),))
    if user:
        link = f"{config.APP_URL}/#/reset?token={sec.create_token(user['id'], 30, 'reset', {'fp': (user['password_hash'] or 'x')[-10:]})}"
        sent = send_mail(user["email"], "Reset your Pramaan AI password", f"Use this link to reset your password (valid 30 minutes):\n\n{link}\n\nIf you did not ask for this, ignore this email.")
        audit(user["id"], "password_reset_requested", "emailed" if sent else "not emailed")
        if not sent and config.DEV_MODE:
            resp["dev_reset_link"] = link  # DEV_MODE only: lets you test without an SMTP server
    return resp


@router.post("/reset", dependencies=[Depends(sec.rate_limit("reset", 8))])
def reset(body: ResetIn):
    data = sec.decode_token(body.token, "reset")
    user = db.q1("SELECT * FROM users WHERE id=?", (int(data["sub"]),))
    if not user or (user["password_hash"] or "x")[-10:] != data.get("fp"):
        raise HTTPException(400, "This reset link was already used or is no longer valid.")
    errs = sec.validate_password(body.new_password, user["email"])
    if errs:
        raise HTTPException(422, "Password needs: " + ", ".join(errs) + ".")
    db.ex("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=0 WHERE id=?", (sec.hash_password(body.new_password), user["id"]))
    sec.revoke_all_sessions(user["id"])
    audit(user["id"], "password_reset")
    return {"message": "Password updated. You can sign in now."}


@router.post("/verify")
def verify_email(body: TokenIn):
    data = sec.decode_token(body.token, "verify")
    db.ex("UPDATE users SET email_verified=1 WHERE id=?", (int(data["sub"]),))
    audit(int(data["sub"]), "email_verified")
    return {"message": "Email verified. You can sign in now."}


@router.post("/resend-verification", dependencies=[Depends(sec.rate_limit("resend", 3))])
def resend(body: ForgotIn):
    user = db.q1("SELECT * FROM users WHERE email=?", (body.email.lower(),))
    dev = _send_verification(user) if user and not user["email_verified"] else None
    return {"message": "If that account needs verification, a new link was sent.", "dev_verify_link": dev}


# ---------------- optional TOTP 2FA ----------------
@router.post("/2fa/setup")
def twofa_setup(user: dict = Depends(sec.current_user)):
    secret = totp.new_secret()
    db.ex("UPDATE users SET totp_secret=?, totp_enabled=0 WHERE id=?", (secret, user["id"]))
    uri = totp.provisioning_uri(secret, user["email"])
    return {"secret": secret, "otpauth_uri": uri, "qr": totp.qr_svg_data_uri(uri)}


@router.post("/2fa/enable")
def twofa_enable(body: TotpIn, user: dict = Depends(sec.current_user)):
    if not user["totp_secret"] or not totp.verify(user["totp_secret"], body.code):
        raise HTTPException(400, "That code is not correct. Check the time on your phone and try again.")
    db.ex("UPDATE users SET totp_enabled=1 WHERE id=?", (user["id"],))
    audit(user["id"], "2fa_enabled")
    return {"enabled": True}


@router.post("/2fa/disable")
def twofa_disable(body: TotpIn, user: dict = Depends(sec.current_user)):
    if not user["totp_enabled"] or not totp.verify(user["totp_secret"], body.code):
        raise HTTPException(400, "That code is not correct.")
    db.ex("UPDATE users SET totp_enabled=0, totp_secret=NULL WHERE id=?", (user["id"],))
    audit(user["id"], "2fa_disabled")
    return {"enabled": False}
