import calendar
from datetime import datetime, timezone
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from admin_routes import router as admin_router
from database import engine, get_db
import models
from security import sign_payload, verify_signature, derive_device_secret

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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https://*.supabase.co;"
    )
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

@app.post("/api/v1/rules")
def get_secure_rules(request: Request, body: dict, db: Session = Depends(get_db)):
    # 1. Extract the exact keys sent by background.js (license_key, device_id, envelope)
    license_key = body.get("license_key")
    device_id = body.get("device_id")
    envelope = body.get("envelope")
    incoming_signature = request.headers.get("X-Signature")

    if not license_key or not device_id or not envelope or not incoming_signature:
        raise HTTPException(status_code=400, detail="Missing required payload parameters")

    # 2. Database validation
    lic = db.query(models.License).filter(models.License.license_key == license_key, models.License.active == True).first()
    if not lic:
        raise HTTPException(status_code=403, detail="Invalid license")

    device = db.query(models.Device).filter(models.Device.license_id == lic.id, models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=403, detail="Device not registered")

    # 3. CRITICAL: Match JavaScript's JSON.stringify() behavior exactly.
    # JavaScript's JSON.stringify() sorts keys and removes spaces.
    # Python's json.dumps() must use separators=(',', ':') and sort_keys=True
    serialized_envelope = json.dumps(envelope, separators=(',', ':'), sort_keys=True)

    # 4. Cryptographically verify using the derived secret
    derived_secret_bytes = derive_device_secret(device_id)

    # Compute HMAC-SHA256
    computed_hash = hmac.new(
        derived_secret_bytes,
        serialized_envelope.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # 5. Compare signatures
    if not hmac.compare_digest(computed_hash, incoming_signature):
        raise HTTPException(status_code=403, detail="Cryptographic signature mismatch")

    # Success: update and return rules
    device.last_seen = datetime.now(timezone.utc)
    db.commit()

    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]"
        ]
    }

# -------------------------------------------------
# Static Files & Lifecycle
# -------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
