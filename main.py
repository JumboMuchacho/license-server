import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# --- SlowAPI Error Handler Setup ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(admin_router)
app.include_router(billing_router)

# --- Routes ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/api/v1/register")
@limiter.limit("20/minute")
def register_device(request: Request, body: RegistrationSchema, db: Session = Depends(get_db)):
    existing = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if existing:
        return {"status": "already_registered", "device_id": existing.device_id}
    new_device = models.Device(device_id=body.device_id, token_balance=0, active=True)
    db.add(new_device)
    db.commit()
    return {"status": "registered", "device_id": new_device.device_id}

@app.get("/api/v1/status")
@limiter.limit("60/minute")
def get_device_status(request: Request, device_id: str, db: Session = Depends(get_db)):
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
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device:
        raise HTTPException(status_code=403, detail="Unauthorized Device Identity.")
    if not device.active or device.token_balance <= 0:
        raise HTTPException(status_code=403, detail="Forbidden or Insufficient balances.")
    return {
        "isActive": True,
        "rules": ["//div[contains(@class, 'message')][contains(text(), 'There is no USDT transaction')]"]
    }

@app.post("/api/v1/billing/consume-token")
@limiter.limit("60/minute")
def consume_token(request: Request, body: ConsumeTokenRequest, db: Session = Depends(get_db)):
    already_paid = db.query(models.ProcessedTransaction).filter(
        models.ProcessedTransaction.txn_id == body.txn_id
    ).first()
    if already_paid:
        return {"success": True, "message": "Already paid"}
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device or device.token_balance <= 0:
        raise HTTPException(status_code=403, detail="Insufficient balance")
    device.token_balance -= 1
    db.add(models.ProcessedTransaction(txn_id=body.txn_id, device_id=body.device_id))
    db.commit()
    return {"success": True, "new_balance": device.token_balance}

# --- Static Files & Admin UI ---
# This serves files from the 'admin' directory to the '/admin' route
app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")

@app.get("/admin")
async def get_admin():
    return FileResponse("admin/index.html")

# --- DEBUG: Route Registration Check ---
# Kept at the bottom so 'app' is fully initialized
for route in app.routes:
    print(f"Registered route: {route.path}")
