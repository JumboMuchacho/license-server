import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# --- SlowAPI Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- Project Modules ---
from database import engine, get_db, init_db
import models
from admin_routes import router as admin_router
from billing_routes import router as billing_router
from security import verify_raw_signature, sign_payload
from schemas import RegistrationSchema, ConsumeTokenRequest

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
    title="Taptap Server Admin",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json"
)

# --- CORS Middleware ---
# Replace the wildcard with your specific Extension ID when ready for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(admin_router)
app.include_router(billing_router)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

@app.get("/")
def root():
    return RedirectResponse("/admin-ui")

@app.get("/admin-ui")
def admin_ui():
    return FileResponse("static/admin/index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

# -------------------------------------------------
# Operational Routes
# -------------------------------------------------

@app.post("/api/v1/register")
@limiter.limit("20/minute")
def register_device(request: Request, body: RegistrationSchema, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        device = models.Device(
            device_id=body.device_id,
            token_balance=0,
            active=True,
            last_seen=datetime.now(timezone.utc)
        )
        db.add(device)
    else:
        device.last_seen = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "device_id": device.device_id, "token_balance": device.token_balance}

@app.get("/api/v1/status")
def get_device_status(device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"token_balance": device.token_balance, "is_active": device.token_balance > 0}

@app.post("/api/v1/rules")
@limiter.limit("200/minute")
def get_secure_rules(request: Request, body: dict, x_auth_token: str = Header(...), db: Session = Depends(get_db)):
    device_id = body.get("device_id")
    timestamp = body.get("timestamp")
    if not device_id or not timestamp or not x_auth_token:
        raise HTTPException(status_code=400, detail="Missing elements.")
    if abs(int(time.time()) - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Request expired.")
    if not verify_raw_signature(device_id, int(timestamp), x_auth_token):
        raise HTTPException(status_code=403, detail="Signature mismatch.")

    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if device:
        device.last_seen = datetime.now(timezone.utc)
        db.commit()
    return {
        "isActive": True,
        "rules": ["//div[contains(@class, 'message')][contains(text(), 'There is no USDT transaction')]"]
    }

@app.post("/api/v1/billing/consume-token")
@limiter.limit("100/minute")
def consume_token(request: Request, body: ConsumeTokenRequest, x_auth_token: str = Header(...), db: Session = Depends(get_db)):
    if not verify_raw_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid signature.")
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device or not device.active or device.token_balance <= 0:
        raise HTTPException(status_code=403, detail="Forbidden or Insufficient balance.")
    device.token_balance -= 1
    device.last_seen = datetime.now(timezone.utc)
    db.commit()

    auth_timestamp = int(time.time())
    server_signature = sign_payload({"device": body.device_id, "action": "PLAY_ALARM", "timestamp": auth_timestamp})
    return {"status": "authorized", "timestamp": auth_timestamp, "signature": server_signature}
