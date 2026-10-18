
from backend import config
from backend import database as db
from backend import security as sec
from backend.services import totp

from .conftest import PW, Client


def test_weak_password_and_duplicate(uniq):
    c = Client()
    r = c.post("/api/auth/register", json={"name": "Asha", "email": f"a{uniq}@x.in", "password": "short", "role": "patient"})
    assert r.status_code == 422
    c.signup(f"a{uniq}@x.in")
    r = c.post("/api/auth/register", json={"name": "Asha G", "email": f"A{uniq}@x.in", "password": PW, "role": "patient"})
    assert r.status_code == 409


def test_cookies_are_httponly_and_no_token_in_body(uniq):
    c = Client()
    r = c.signup(f"c{uniq}@x.in")
    assert "token" not in r.json()
    sc = r.headers.get_list("set-cookie")
    assert any(s.startswith("pr_at=") and "httponly" in s.lower() and "samesite=lax" in s.lower() for s in sc)
    assert any(s.startswith("pr_rt=") and "httponly" in s.lower() for s in sc)
    assert any(s.startswith("pr_csrf=") and "httponly" not in s.lower() for s in sc)


def test_csrf_required_for_unsafe_methods(patient):
    assert patient.c.post("/api/auth/logout").status_code == 403  # no X-CSRF-Token header
    assert patient.post("/api/auth/logout").status_code == 200


def test_wrong_portal_is_rejected(biller, uniq):
    email = f"biller{uniq}@clinic.in"
    c = Client()
    assert c.post("/api/auth/login", json={"email": email, "password": PW, "portal": "patient"}).status_code == 403
    assert c.post("/api/auth/login", json={"email": email, "password": PW, "portal": "biller"}).status_code == 200


def test_lockout_after_five_failures(patient, uniq):
    email = f"patient{uniq}@mail.com"
    c = Client()
    for _ in range(config.LOGIN_MAX_ATTEMPTS):
        assert c.post("/api/auth/login", json={"email": email, "password": "wrongpass1"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 423


def test_logout_revokes_access_token(patient):
    at = patient.c.cookies.get(sec.ACCESS_COOKIE)
    assert patient.get("/api/auth/me").status_code == 200
    patient.post("/api/auth/logout")
    other = Client()
    assert other.get("/api/auth/me", headers={"Authorization": f"Bearer {at}"}).status_code == 401


def test_refresh_rotates_and_replay_revokes_everything(uniq):
    c = Client()
    c.signup(f"r{uniq}@x.in")
    old_rt = c.c.cookies.get(sec.REFRESH_COOKIE)
    r = c.post("/api/auth/refresh")
    assert r.status_code == 200
    new_rt = c.c.cookies.get(sec.REFRESH_COOKIE)
    assert new_rt and new_rt != old_rt
    # an attacker replays the OLD refresh token
    atk = Client()
    atk.c.cookies.set(sec.REFRESH_COOKIE, old_rt, path="/api/auth")
    atk.c.cookies.set(sec.CSRF_COOKIE, "x" * 10)
    bad = atk.c.post("/api/auth/refresh", headers={"X-CSRF-Token": "x" * 10})
    assert bad.status_code == 401
    # the legitimate (rotated) token is now dead as well: all sessions were revoked
    assert c.post("/api/auth/refresh").status_code == 401


def test_refresh_requires_csrf(patient):
    assert patient.c.post("/api/auth/refresh").status_code == 403


def test_password_reset_is_single_use_and_revokes_sessions(patient, uniq):
    email = f"patient{uniq}@mail.com"
    f = Client().post("/api/auth/forgot", json={"email": email}).json()
    tok = f["dev_reset_link"].split("token=")[1]
    c = Client()
    assert c.post("/api/auth/reset", json={"token": tok, "new_password": "BrandNew#Pass5"}).status_code == 200
    assert c.post("/api/auth/reset", json={"token": tok, "new_password": "BrandNew#Pass6"}).status_code == 400
    assert patient.post("/api/auth/refresh").status_code == 401  # old sessions revoked
    assert Client().post("/api/auth/login", json={"email": email, "password": "BrandNew#Pass5"}).status_code == 200


def test_forgot_does_not_reveal_unknown_email():
    r = Client().post("/api/auth/forgot", json={"email": "nobody@nowhere.com"}).json()
    assert "dev_reset_link" not in r and "registered" in r["message"]


def test_dev_link_hidden_when_dev_mode_off(patient, uniq, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    r = Client().post("/api/auth/forgot", json={"email": f"patient{uniq}@mail.com"}).json()
    assert "dev_reset_link" not in r


def test_totp_rfc6238_vector():
    # RFC 6238 appendix B, SHA1, secret "12345678901234567890", T=59 -> 94287082 (8 digits); our 6-digit code is its last 6 digits
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp.totp_now(secret, at=59) == "287082"


def test_two_factor_flow(uniq):
    c = Client()
    c.signup(f"t{uniq}@x.in")
    s = c.post("/api/auth/2fa/setup").json()
    assert s["qr"].startswith("data:image/svg+xml") and s["otpauth_uri"].startswith("otpauth://")
    assert c.post("/api/auth/2fa/enable", json={"code": "000000"}).status_code == 400
    assert c.post("/api/auth/2fa/enable", json={"code": totp.totp_now(s["secret"])}).status_code == 200
    login = Client()
    r = login.post("/api/auth/login", json={"email": f"t{uniq}@x.in", "password": PW})
    assert r.status_code == 401 and r.json()["need_2fa"] is True
    assert login.post("/api/auth/login", json={"email": f"t{uniq}@x.in", "password": PW, "totp_code": "111111"}).status_code == 401
    ok = login.post("/api/auth/login", json={"email": f"t{uniq}@x.in", "password": PW, "totp_code": totp.totp_now(s["secret"])})
    assert ok.status_code == 200 and ok.json()["user"]["totp_enabled"] is True


def test_email_verification_toggle(uniq, monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_VERIFIED", True)
    c = Client()
    r = c.post("/api/auth/register", json={"name": "Ver Ified", "email": f"v{uniq}@x.in", "password": PW, "role": "patient"}).json()
    assert r["verification_required"] and r["dev_verify_link"]
    assert c.post("/api/auth/login", json={"email": f"v{uniq}@x.in", "password": PW}).status_code == 403
    tok = r["dev_verify_link"].split("token=")[1]
    assert c.post("/api/auth/verify", json={"token": tok}).status_code == 200
    assert c.post("/api/auth/login", json={"email": f"v{uniq}@x.in", "password": PW}).status_code == 200


def test_admin_cannot_be_created_via_signup(uniq):
    r = Client().post("/api/auth/register", json={"name": "Evil Admin", "email": f"e{uniq}@x.in", "password": PW, "role": "admin"})
    assert r.status_code == 422


def test_admin_routes_are_role_gated(biller, uniq):
    assert biller.get("/api/admin/users").status_code == 403
    assert Client().get("/api/admin/users").status_code == 401
    email = f"admin{uniq}@pramaan-ai.org"
    db.ex("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,?,1)", ("Admin", email, sec.hash_password(PW), "admin"))
    a = Client()
    assert a.post("/api/auth/login", json={"email": email, "password": PW, "portal": "admin"}).status_code == 200
    assert a.get("/api/admin/overview").json()["users"] >= 2
    assert "events" in a.get("/api/admin/audit").json()
    assert a.get("/api/admin/system").json()["status"] == "ok"
    assert "messages" in a.get("/api/admin/messages").json()
    assert a.get("/api/admin/users").status_code == 200
