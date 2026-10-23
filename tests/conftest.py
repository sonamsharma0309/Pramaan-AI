"""Shared fixtures. Each test session uses a fresh temp database; external services are always mocked."""
import os
import tempfile

# Keep the tests independent of anyone's local .env. config.py only fills in a value
# from .env when the variable is not already set, so every setting that could reach an
# external service or a real database is blanked here, and every behaviour switch is
# pinned to its built-in default. Explicit test settings further down still win.
os.environ.update({
    # blanked: external services and real databases
    "LLM_PROVIDER": "", "GEMINI_API_KEY": "", "OPENAI_COMPAT_BASE_URL": "", "OPENAI_COMPAT_API_KEY": "",
    "OPENAI_COMPAT_MODEL": "", "GOOGLE_CLIENT_ID": "", "CONTACT_TO": "", "SMTP_USER": "", "SMTP_PASSWORD": "",
    "DATABASE_URL": "", "SECRET_KEY": "", "JWT_SECRET": "", "CORS_ORIGINS": "",
    # pinned to the built-in defaults
    "COOKIE_SECURE": "false", "REQUIRE_VERIFIED": "false", "DEIDENTIFY_BEFORE_LLM": "true",
    "EMBEDDINGS": "false", "FHIR_ENABLED": "false", "ACCESS_TOKEN_MINUTES": "15",
    "REFRESH_TOKEN_DAYS": "7", "MAX_UPLOAD_MB": "5", "LOGIN_MAX_ATTEMPTS": "5", "LOGIN_LOCK_MINUTES": "15",
})

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["DEV_MODE"] = "true"
os.environ["RATE_API_PER_MIN"] = "100000"
os.environ["RATE_AUTH_PER_MIN"] = "100000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import config  # noqa: E402
from backend import database as db
from backend import security as sec
from backend.main import app  # noqa: E402

PW = "Strong#Pass9"


class Client:
    """TestClient wrapper that behaves like the browser: keeps cookies and echoes the CSRF cookie in a header."""

    def __init__(self):
        self.c = TestClient(app)

    def _h(self, kw):
        h = dict(kw.pop("headers", {}) or {})
        tok = self.c.cookies.get(sec.CSRF_COOKIE)
        if tok and "X-CSRF-Token" not in h:
            h["X-CSRF-Token"] = tok
        return h

    def get(self, url, **kw):
        return self.c.get(url, headers=self._h(kw), **kw)

    def post(self, url, **kw):
        return self.c.post(url, headers=self._h(kw), **kw)

    def patch(self, url, **kw):
        return self.c.patch(url, headers=self._h(kw), **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self._h(kw), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._h(kw), **kw)

    def signup(self, email, role="patient", org="Test Clinic", name="Test User", invite=""):
        body = {"name": name, "email": email, "password": PW, "role": role, "org": org if role == "biller" and not invite else "", "invite_code": invite}
        r = self.post("/api/auth/register", json=body)
        assert r.status_code == 200, r.text
        return r


@pytest.fixture(scope="session", autouse=True)
def _app():
    with TestClient(app):  # runs lifespan: creates tables + seeds policies
        yield


@pytest.fixture(autouse=True)
def _clean_limits():
    sec.reset_rate_limits()
    yield


_n = {"i": 0}


@pytest.fixture()
def uniq():
    _n["i"] += 1
    return _n["i"]


@pytest.fixture()
def biller(uniq):
    c = Client()
    c.signup(f"biller{uniq}@clinic.in", "biller", org=f"Clinic {uniq}")
    return c


@pytest.fixture()
def patient(uniq):
    c = Client()
    c.signup(f"patient{uniq}@mail.com", "patient")
    return c


@pytest.fixture()
def seeded(biller):
    r = biller.post("/api/claims/seed-demo?sample=main")
    assert r.json()["imported"] == 4
    return biller


def make_admin(email="admin@pramaan-ai.org"):
    uid = db.ex("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,?,1)", ("Admin", email, sec.hash_password(PW), "admin"))
    return uid


__all__ = ["Client", "PW", "config", "make_admin"]
