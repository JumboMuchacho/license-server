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


# Look for your existing get_secure_rules function and replace it with this:

@app.post("/api/v1/rules")
def get_secure_rules(request: Request, body: dict, x_auth_token: str = Header(...), db: Session = Depends(get_db)):
    device_id = body.get("device_id")
    timestamp = body.get("timestamp")

    if not device_id or not timestamp or not x_auth_token:
        raise HTTPException(status_code=400, detail="Missing parameters")

    # --- REPLAY ATTACK MITIGATION ---
    # Rejects requests if the client's timestamp is older than 5 minutes (300 seconds)
    current_time = int(time.time())
    if abs(current_time - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Request expired. Replay attack detected.")

    # --- CRYPTOGRAPHIC VERIFICATION ---
    from security import verify_raw_signature
    if not verify_raw_signature(device_id, timestamp, x_auth_token):
        raise HTTPException(status_code=403, detail="Signature verification failed.")

    # Update device heartbeat
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

# -------------------------------------------------
# Static Files & Lifecycle
# -------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
