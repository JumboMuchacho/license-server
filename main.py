import os
import time
import uuid
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
from billing import MpesaTransaction
from admin_routes import router as admin_router
from billing_routes import router as billing_router
# FIXED: Included RegistrationSchema into parsing layers for rules matching
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
    redoc_url=None if is_production else "/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://iaollkojbfolafoiljaaieijhflbiofi",
        "https://license-server-lewp.onrender.com"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(billing_router)

@app.post("/api/v1/register")
@limiter.limit("5/minute")
def register_device(request: Request, schema: RegistrationSchema, db: Session = Depends(get_db)):
    try:
        clean_id = str(uuid.UUID(schema.device_id.strip()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed structure registration attempt rejected.")

    existing = db.query(models.Device).filter(models.Device.device_id == clean_id).first()
    if existing:
        return {"status": "recognized", "device_id": existing.device_id, "token_balance": existing.token_balance}

    new_device = models.Device(device_id=clean_id, token_balance=0, active=True)
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return {"status": "registered", "device_id": new_device.device_id, "token_balance": new_device.token_balance}

@app.get("/api/v1/status")
@limiter.limit("60/minute")
def get_status(request: Request, device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device context not found.")

    latest_txn = db.query(MpesaTransaction).filter(MpesaTransaction.device_id == device_id).order_by(MpesaTransaction.created_at.desc()).first()
    payment_status = latest_txn.status if latest_txn else "NONE"

    return {
        "device_id": device.device_id,
        "token_balance": device.token_balance,
        "active": device.active,
        "latest_payment_status": payment_status
    }

@app.post("/api/v1/rules")
@limiter.limit("60/minute")
def get_rules(request: Request, body: RegistrationSchema, db: Session = Depends(get_db)):
    # 1. Fetch device profile
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        raise HTTPException(status_code=403, detail="Unauthorized Device Identity.")

    # 2. Check token balance or active status strictly on the server side
    if not device.active or device.token_balance <= 0:
        raise HTTPException(status_code=403, detail="Forbidden or Insufficient balances.")

    # 3. Securely deduct token *before* giving away tracking data
    device.token_balance -= 1
    device.created_at = datetime.now(timezone.utc)
    db.commit()

    # 4. Return matching naming convention (active) to the extension
    return {
        "active": device.active,
        "token_balance": device.token_balance,
        "rules": ["//div[contains(@class, 'message')][contains(text(), 'There is no USDT transaction')]"]
    }
