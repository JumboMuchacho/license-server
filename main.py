import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Header
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
from security import verify_signature, sign_payload

load_dotenv()

# Initialize the Limiter using the client's remote IP address
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="License Server")

# Set up SlowAPI state and custom exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include Admin Control Routes
app.include_router(admin_router)

# Mount UI Asset Directory safely if it exists
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------------------------------------
# Security Headers Middleware
# -------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# -------------------------------------------------
# Request Payload Schemas
# -------------------------------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    version: Optional[str] = None


class ConsumeTokenRequest(BaseModel):
    device_id: str
    timestamp: int

# -------------------------------------------------
# Operational Routes
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


@app.post("/api/v1/register")
@limiter.limit("20/minute")
def register_device(request: Request, body: VerifyRequest, db: Session = Depends(get_db)):
    """
    Validates license tokens and links the current unique hardware configuration identifier.
    """
    # 1. Lookup the target key allocation details
    lic = db.query(models.License).filter(models.License.license_key == body.license_key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License key not found.")

    if not lic.active:
        raise HTTPException(status_code=403, detail="License key has been suspended.")

    # Check expiration limits safely
    if lic.expires_at and lic.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="License key has expired.")

    # 2. Check if the device profile is already bound to this license key
    device = db.query(models.Device).filter(
        models.Device.license_id == lic.id,
        models.Device.device_id == body.device_id
    ).first()

    if not device:
        # Check overall volume limits per individual key registration slot allocation limits
        current_allocations = db.query(models.Device).filter(models.Device.license_id == lic.id).count()
        if current_allocations >= lic.max_devices:
            raise HTTPException(status_code=403, detail="Device registration limit exceeded for this license.")

        # Instantiate a secure tracking context structure
        device = models.Device(
            license_id=lic.id,
            device_id=body.device_id,
            last_seen=datetime.now(timezone.utc)
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        # Touch runtime updates
        device.last_seen = datetime.now(timezone.utc)
        db.commit()

    return {
        "status": "success",
        "message": "Device successfully registered and validated."
    }


@app.post("/api/v1/rules")
@limiter.limit("60/minute")
def get_secure_rules(
    request: Request,
    body: dict,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Verifies raw concatenated HMAC strings using derived hardware keys.
    Prevents replay injections via strict timestamp drift inspection thresholds.
    """
    device_id = body.get("device_id")
    timestamp = body.get("timestamp")

    if not device_id or not timestamp or not x_auth_token:
        raise HTTPException(status_code=400, detail="Missing mandatory protocol elements.")

    # --- REPLAY ATTACK MITIGATION ---
    try:
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:
            raise HTTPException(status_code=401, detail="Request timeline expired. Potential replay attack.")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed payload timestamps provided.")

    # --- CRYPTOGRAPHIC VERIFICATION ---
    if not verify_raw_signature(device_id, int(timestamp), x_auth_token):
        raise HTTPException(status_code=403, detail="Cryptographic verification payload signature mismatch.")

    # Match system device mapping records context profiles safely
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if device:
        device.last_seen = datetime.now(timezone.utc)
        db.commit()

    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]"
        ]
    }


@app.post("/api/v1/billing/consume-token")
@limiter.limit("30/minute")
def consume_token(
    request: Request,
    body: ConsumeTokenRequest,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Deducts 1 token from the license balance on successful element match,
    and returns a cryptographically signed authorization packet to fire the alarm.
    """
    # 1. Verify incoming request signature to prevent spoofing
    if not verify_signature(body.device_id, body.timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    # 2. Find device and its bound license context
    device = db.query(models.Device).filter(models.Device.device_id == body.device_id).first()
    if not device or not device.license:
        raise HTTPException(status_code=404, detail="Device registration profile not found.")

    lic = device.license
    if not lic.active:
        raise HTTPException(status_code=403, detail="License has been suspended.")

    # 3. Check token balance status
    if lic.token_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient token balance. Please top up via M-Pesa.")

    # 4. Deduct token and commit transaction securely
    lic.token_balance -= 1
    device.last_seen = datetime.now(timezone.utc)
    db.commit()

    # 5. Build confirmation payload and sign it using our system signature architecture
    auth_timestamp = int(time.time())

    payload_to_sign = {
        "device": body.device_id,
        "action": "PLAY_ALARM",
        "timestamp": auth_timestamp
    }

    server_signature = sign_payload(payload_to_sign)

    return {
        "status": "authorized",
        "timestamp": auth_timestamp,
        "signature": server_signature
    }
