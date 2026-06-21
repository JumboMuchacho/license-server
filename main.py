import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

import models
from admin_routes import router as admin_router
from billing_routes import router as billing_router
from database import engine, get_db, init_db
from schemas import ConsumeTokenRequest, RegistrationSchema, StatusRequest
from security import verify_device_request

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"CRITICAL: Could not connect to database: {e}")
    yield
    engine.dispose()


is_production = os.getenv("ENV") == "production"
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Taptap License Server",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

default_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if not default_origins and not is_production:
    default_origins = ["http://localhost:10000", "http://127.0.0.1:10000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Token"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(admin_router)
app.include_router(billing_router)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


def _content_script_matches() -> list[str]:
    raw = os.getenv(
        "CONTENT_SCRIPT_MATCHES",
        "http://localhost/*,http://127.0.0.1/*,file:///*",
    )
    return [match.strip() for match in raw.split(",") if match.strip()]


def _detection_rules() -> list[str]:
    raw = os.getenv(
        "DETECTION_RULES",
        "//div[contains(@class, 'message')][contains(text(), 'There is no USDT transaction')]",
    )
    return [rule.strip() for rule in raw.split("||") if rule.strip()]


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.get("/")
def root():
    return RedirectResponse("/admin-ui")


@app.get("/admin-ui")
def admin_ui():
    return FileResponse("static/admin/index.html")


@app.get("/admin/config")
def admin_public_config():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_anon_key:
        raise HTTPException(status_code=503, detail="Admin auth is not configured.")
    return {"supabase_url": supabase_url, "supabase_anon_key": supabase_anon_key}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/register")
@limiter.limit("20/minute")
def register_device(
    request: Request,
    body: RegistrationSchema,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db),
):
    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device:
        device = models.Device(
            device_id=body.device_id,
            token_balance=0,
            active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(device)
    else:
        device.created_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "success",
        "device_id": device.device_id,
        "token_balance": device.token_balance,
    }


@app.post("/api/v1/status")
@limiter.limit("120/minute")
def get_device_status(
    request: Request,
    body: StatusRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db),
):
    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device:
        return {"token_balance": 0, "is_active": False}

    return {
        "token_balance": device.token_balance,
        "is_active": device.active and device.token_balance > 0,
    }


@app.post("/api/v1/config")
@limiter.limit("60/minute")
def get_client_config(
    request: Request,
    body: StatusRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db),
):
    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device or not device.active:
        raise HTTPException(status_code=403, detail="Device is not active.")

    return {"matches": _content_script_matches()}


@app.post("/api/v1/rules")
@limiter.limit("200/minute")
def get_secure_rules(
    request: Request,
    body: StatusRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db),
):
    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered.")
    if not device.active or device.token_balance <= 0:
        raise HTTPException(status_code=403, detail="Insufficient token balance.")

    device.created_at = datetime.now(timezone.utc)
    db.commit()
    return {"isActive": True, "rules": _detection_rules()}


@app.post("/api/v1/billing/consume-token")
@limiter.limit("100/minute")
def consume_token(
    request: Request,
    body: ConsumeTokenRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db),
):
    verify_device_request(body.device_id, body.timestamp, x_auth_token)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == body.device_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=410, detail="Device not found in registry.")
    if not device.active or device.token_balance <= 0:
        raise HTTPException(
            status_code=403, detail="Forbidden or Insufficient balance."
        )

    device.token_balance -= 1
    device.created_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "authorized", "token_balance": device.token_balance}
