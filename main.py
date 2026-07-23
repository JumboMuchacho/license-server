import os
import time
import json
import logging
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "https://license-server-lewp.onrender.com,"
    "chrome-extension://iaollkojbfolafoiljaaieijhflbiofi",
).split(",")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

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
from datetime import datetime, timezone, timedelta

# ==========================
# Online Presence Tracking
# ==========================

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database tables initialized successfully.")
    except Exception:
        logger.exception("Database initialization failed.")
        raise

    yield

    logger.info("Server shutting down... Bye bye Batman!")
    engine.dispose()
    logger.info(
    "Boot sequence initialized.. Hello Batman! (%s)",
    "Production" if is_production else "Development"
)

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
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Email Validation
# ==========================

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# --- Include Routers ---

app.include_router(admin_router)
app.include_router(billing_router)

# ==========================
# Routes
# ==========================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


@app.post("/api/v1/register")
@limiter.limit("20/minute")
def register_device(
    request: Request,
    body: RegistrationSchema,
    db: Session = Depends(get_db)
):
    device_id = body.device_id.strip().lower()

    if not EMAIL_REGEX.fullmatch(device_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid email address."
        )

    existing = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id)
        .first()
    )

    if existing:
        return {
            "status": "already_registered",
            "device_id": existing.device_id
        }

    clean_id = body.device_id.strip().lower()

    new_device = models.Device(
        device_id=clean_id,
        token_balance=0,
        active=True
    )

    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return {
        "status": "registered",
        "device_id": new_device.device_id
    }

@app.post("/api/v1/heartbeat")
async def heartbeat(
    payload: RegistrationSchema,
    db: Session = Depends(get_db)
):
    device_id = payload.device_id.strip().lower()

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    device.last_seen = datetime.utcnow()

    db.commit()

    return {
        "success": True
    }

@app.get("/api/v1/status")
@limiter.limit("15/minute")
async def get_device_status(
    request: Request,
    device_id: str,
    db: Session = Depends(get_db)
):
    device_id = device_id.strip().lower()

    if not EMAIL_REGEX.fullmatch(device_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid device identifier."
        )

    cache_key = f"status:{device_id}"

    cached = await redis.get(cache_key)

    if cached:
        return json.loads(cached)

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device context not found."
        )

    latest_txn = (
        db.query(MpesaTransaction)
        .filter(MpesaTransaction.device_id == device_id)
        .order_by(MpesaTransaction.created_at.desc())
        .first()
    )

    payment_status = (
        latest_txn.status
        if latest_txn
        else "NONE"
    )

    cutoff = datetime.utcnow() - timedelta(minutes=3)

    online_users = (
        db.query(models.Device)
        .filter(
            models.Device.last_seen.isnot(None),
            models.Device.last_seen >= cutoff
        )
        .count()
    )

    online = (
        device.last_seen is not None
        and device.last_seen >= cutoff
    )

    return {
        "device_id": device.device_id,
        "token_balance": device.token_balance,
        "active": device.active,
        "online": online,
        "online_users": online_users,
        "last_seen": (
            device.last_seen.isoformat()
            if device.last_seen
            else None
        ),
        "latest_payment_status": payment_status
    }
    await redis.setex(
        cache_key,
        5,
        json.dumps(response)
    )

    return response


@app.post("/api/v1/rules")
@limiter.limit("20/minute")
def get_rules(
    request: Request,
    body: RegistrationSchema,
    db: Session = Depends(get_db)
):
    device_id = body.device_id.strip().lower()

    if not EMAIL_REGEX.fullmatch(device_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid device identifier."
        )

    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized Device Identity."
        )

    if not device.active:
        raise HTTPException(
            status_code=403,
            detail="Device disabled."
        )

    if device.token_balance <= 0:
        raise HTTPException(
            status_code=403,
            detail="Insufficient balance."
        )

    default_config = {
        "orderLabel": "Order Number",
        "timeLabel": "Create Time"
    }

    config_str = os.getenv(
        "TARGET_SELECTOR_CONFIG",
        json.dumps(default_config)
    )

    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        config = default_config

    return {
        "isActive": True,
        "labels": config
    }
@app.post("/api/v1/billing/consume-token")
@limiter.limit("20/minute")
def consume_token(
    request: Request,
    body: ConsumeTokenRequest,
    db: Session = Depends(get_db),
):
    device_id = body.device_id.strip().lower()

    already_paid = (
        db.query(models.ConsumedToken)
        .filter(models.ConsumedToken.txn_id == body.txn_id)
        .first()
    )

    if already_paid:
        return {
            "success": True,
            "message": "Already paid",
        }

    # -------------------------------------------------------
    # Atomic token deduction
    # -------------------------------------------------------
    updated = (
        db.query(models.Device)
        .filter(
            models.Device.device_id == device_id,
            models.Device.token_balance > 0,
        )
        .update(
            {
                models.Device.token_balance:
                    models.Device.token_balance - 1
            },
            synchronize_session=False,
        )
    )

    if updated != 1:
        raise HTTPException(
            status_code=403,
            detail="Insufficient balance",
        )

    db.add(
        models.ConsumedToken(
            txn_id=body.txn_id,
            device_id=device_id,
        )
    )

    db.commit()

    # Reload device to get the updated balance
    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id)
        .first()
    )

    return {
        "success": True,
        "new_balance": device.token_balance,
    }

# --- Static Files & Admin UI ---
# This serves files from the 'admin' directory to the '/admin' route
app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")
app.mount("/website", StaticFiles(directory="website"), name="website")

logger.info("Routes registered successfully.")
