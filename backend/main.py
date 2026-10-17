"""Pramaan AI - FastAPI application entrypoint. Serves the API and the single-page frontend."""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from . import database as db
from . import security as sec
from .data.seed import seed_policies
from .routers import admin, appeals, auth, claims, codes, dashboard, exports, fhir, icd, misc, notifications, policies
from .services.audit import client_ip, request_id

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
log = logging.getLogger("pramaan")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://accounts.google.com https://apis.google.com; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; font-src 'self' https://fonts.gstatic.com; "
       "img-src 'self' data: https://*.googleusercontent.com; connect-src 'self' https://accounts.google.com; frame-src https://accounts.google.com; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    seed_policies()
    log.info("Pramaan AI started (db=%s, ai=%s)", "sqlite" if config.IS_SQLITE else "postgresql", config.llm_provider() or "off")
    yield


app = FastAPI(title="Pramaan AI", version=misc.VERSION, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
if config.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"])


@app.middleware("http")
async def middleware(request: Request, call_next):
    rid = uuid.uuid4().hex[:12]
    request_id.set(rid)
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "-"))
    client_ip.set(ip)
    if request.url.path.startswith("/api/") and not sec.hit(f"api:{ip}", config.RATE_API_PER_MIN):
        return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429, headers={"X-Request-ID": rid})
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers.update({"X-Request-ID": rid, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin",
                         "Permissions-Policy": "camera=(), microphone=(), geolocation=()", "Content-Security-Policy": CSP})
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
        resp.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/api/"):
        log.info("rid=%s %s %s -> %s %.0fms", rid, request.method, request.url.path, resp.status_code, (time.perf_counter() - t0) * 1000)
    return resp


for r in (auth, claims, appeals, policies, dashboard, codes, exports, notifications, admin, icd, fhir, misc):
    app.include_router(r.router)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": getattr(exc, "detail", "Not found")}, status_code=404)
    return FileResponse(FRONTEND / "index.html")


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(FRONTEND / "favicon.svg", media_type="image/svg+xml")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")
