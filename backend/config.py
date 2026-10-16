"""Central configuration. Reads .env (if present) and environment variables.

Every setting has a safe default so the app also runs with an empty .env (offline fallback mode).
"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def _load_dotenv() -> None:
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.split(" #")[0].strip().strip('"').strip("'"))


_load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{(DATA_DIR / 'pramaan.db').as_posix()}"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
IS_SQLITE = DATABASE_URL.startswith("sqlite")


def _secret() -> str:
    key = (os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET") or "").strip()
    if key:
        return key
    f = DATA_DIR / ".secret_key"
    if f.exists():
        return f.read_text().strip()
    key = secrets.token_urlsafe(64)
    f.write_text(key)
    return key


SECRET_KEY = _secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = env_int("ACCESS_TOKEN_MINUTES", 15)
REFRESH_TOKEN_DAYS = env_int("REFRESH_TOKEN_DAYS", 7)
COOKIE_SECURE = env_bool("COOKIE_SECURE", False)
DEV_MODE = env_bool("DEV_MODE", False)
REQUIRE_VERIFIED = env_bool("REQUIRE_VERIFIED", False)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

APP_URL = (os.getenv("APP_URL") or os.getenv("BASE_URL") or "http://localhost:8000").rstrip("/")

# ---- AI letter writer: pick ONE provider (all optional; with none set the built-in cited template is used) ----
# LLM_PROVIDER: "" / "auto" (first provider that has a key: anthropic > gemini > openai_compatible),
#               or force one of: anthropic | gemini | ollama | openai_compatible.   Ollama is never auto-picked.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip().rstrip("/")
OPENAI_COMPAT_API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
OPENAI_COMPAT_MODEL = os.getenv("OPENAI_COMPAT_MODEL", "").strip()
DEIDENTIFY_BEFORE_LLM = env_bool("DEIDENTIFY_BEFORE_LLM", True)
EMBEDDINGS = env_bool("EMBEDDINGS", False)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@pramaan.ai")
CONTACT_TO = os.getenv("CONTACT_TO", "").strip()

FHIR_ENABLED = env_bool("FHIR_ENABLED", False)
FHIR_BASE = os.getenv("FHIR_BASE", "https://hapi.fhir.org/baseR4").rstrip("/")

MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_MB", 5) * 1024 * 1024
LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_LOCK_SECONDS = env_int("LOGIN_LOCK_MINUTES", 15) * 60
RATE_AUTH_PER_MIN = env_int("RATE_AUTH_PER_MIN", 15)
RATE_API_PER_MIN = env_int("RATE_API_PER_MIN", 240)
SITE_NAME = "Pramaan AI"


def llm_provider() -> str:
    """Active AI provider name, or "" when the app should use the offline template. Read at call time (tests patch the values)."""
    p = LLM_PROVIDER
    if p in ("", "auto"):
        if ANTHROPIC_API_KEY:
            return "anthropic"
        if GEMINI_API_KEY:
            return "gemini"
        if OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_MODEL:
            return "openai_compatible"
        return ""
    if p == "anthropic":
        return p if ANTHROPIC_API_KEY else ""
    if p == "gemini":
        return p if GEMINI_API_KEY else ""
    if p == "ollama":
        return p
    if p == "openai_compatible":
        return p if (OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_MODEL) else ""
    return ""


def llm_model() -> str:
    return {"anthropic": ANTHROPIC_MODEL, "gemini": GEMINI_MODEL, "ollama": OLLAMA_MODEL, "openai_compatible": OPENAI_COMPAT_MODEL}.get(llm_provider(), "")


def llm_label() -> str:
    """Short engine label stored with each appeal. Anthropic keeps the historical 'claude' label."""
    return {"anthropic": "claude"}.get(llm_provider(), llm_provider())
