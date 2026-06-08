import os
import time
import calendar
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# --- SlowAPI Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db
import models
from admin_routes import router as admin_router
from security import sign_payload, verify_signature

load_dotenv()

# Initialize the Limiter using the client's remote IP address
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="License Server")

# Set up SlowAPI state and custom exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# -------------------------------------------------
# Security Headers Middleware
# -------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https://*.supabase.co;"
    return response


app.include_router(admin_router)


# -------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------

class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    version: Optional[str] = None


class RulesRequest(BaseModel):
    license_key: str
    device_id: str
    envelope: dict  # Receives the cryptographically structured packet from the client extension


# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.get("/")
def root():
    return RedirectResponse("/admin-ui")


@app.get("/admin-ui")
def admin_ui():
    return FileResponse("static/admin/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


# Limiting to 5 attempts per minute per IP to prevent brute-forcing keys
@app.post("/verify")
@limiter.limit("5/minute")
def verify(request: Request, req: VerifyRequest, db: Session = Depends(get_db)):
    # Use standard naive UTC datetime to seamlessly match your PostgreSQL schema definitions
    now = datetime.utcnow()

    lic = db.query(models.License).filter(
        models.License.license_key == req.license_key,
        models.License.active == True
    ).first()

    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410, detail="License expired")

    device = db.query(models.Device).filter_by(
        license_id=lic.id,
        device_id=req.device_id
    ).first()

    if not device:
        if lic.max_devices is not None and len(lic.devices) >= lic.max_devices:
            raise HTTPException(status_code=403, detail="Device limit reached")

        device = models.Device(
            license_id=lic.id,
            device_id=req.device_id,
            last_seen=now
        )
        db.add(device)
    else:
        device.last_seen = now

    db.commit()

    # -------------------------------------------------
    # Token Lifetime Logic
    # -------------------------------------------------

    if lic.expires_at:
        # Use calendar timegm to extract epoch seconds safely from naive database datetime
        exp_time = int(calendar.timegm(lic.expires_at.utctimetuple()))
    else:
        # Lifetime license fallback → 5 mins
        exp_time = int(time.time()) + 300

    token = {
        "license": req.license_key,
        "device": req.device_id,
        "exp": exp_time
    }

    # Define the payload structure before passing it to the cryptographic signer
    response_payload = {
        "token": token,
        "device": req.device_id
    }

    return {
        "token": token,
        "signature": sign_payload(response_payload),
        "expires_at": f"{lic.expires_at.isoformat()}Z" if lic.expires_at else None
    }


# Limiting to 20 rules synchronization requests per minute per IP
@app.post("/api/v1/rules")
@limiter.limit("20/minute")
async def get_secure_rules(request: Request, req: RulesRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    sig = request.headers.get("X-Signature")

    # 1. Cryptographic client identity validation
    if not sig or not verify_signature(req.envelope, sig):
        raise HTTPException(status_code=403, detail="Invalid request signature")

    # 2. Validate the license status in your database
    lic = db.query(models.License).filter(
        models.License.license_key == req.license_key,
        models.License.active == True
    ).first()

    # If license doesn't exist or is expired, return an empty rules array safely
    if not lic or (lic.expires_at and lic.expires_at < now):
        return {"isActive": False, "rules": []}

    # 3. Verify the device is actually registered to this specific license key
    device_authorized = db.query(models.Device).filter_by(
        license_id=lic.id,
        device_id=req.device_id
    ).first()

    if not device_authorized:
        # Auto-register device if limit headroom is available
        if lic.max_devices is not None and len(lic.devices) >= lic.max_devices:
            return {"isActive": False, "rules": []}

        device_authorized = models.Device(
            license_id=lic.id,
            device_id=req.device_id,
            last_seen=now
        )
        db.add(device_authorized)
    else:
        # Update device telemetry heartbeat
        device_authorized.last_seen = now

    db.commit()

    # 4. SUCCESS: Return the secure layout selectors hidden from public repositories
    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]",
            "//*[contains(text(), 'deposit address')]"
        ]
    }


# -------------------------------------------------
# Static Files & Lifecycle
# -------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
