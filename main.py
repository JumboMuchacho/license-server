import os
import time
from datetime import datetime, timezone
import logging
import hmac
import hashlib
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import local modules
from database import SessionLocal, engine, get_db
import models
from admin_routes import router as admin_router

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        # Note: If this fails, Render logs will show exactly which key is missing
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

# Required Config
DATABASE_URL = require_env("DATABASE_URL")
LICENSE_SECRET = require_env("LICENSE_SECRET")
# Ensure these match your auth.py needs
SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = require_env("SUPABASE_SERVICE_KEY")

OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", 24))

# ----------------------------
# Logging & App Init
# ----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="License Server")

# -------------------------------------------------
# 1. HEALTH CHECK (Render / Load Balancers)
# MUST be defined BEFORE routers or static mounts
# -------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "License Server API running"}

# ----------------------------
# 2. Routers & Static Files
# ----------------------------
# Include Admin Routes (Protected by Supabase Auth)
app.include_router(admin_router)

# Mount the Admin UI (Static Folder)
app.mount(
    "/admin-ui",
    StaticFiles(directory="static/admin", html=True),
    name="admin-ui",
)

# ----------------------------
# 3. Database Initialization
# ----------------------------
@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")

# ----------------------------
# 4. Verification Logic
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None

def sign_payload(payload: dict) -> str:
    """Standardized JSON signing."""
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")

    return hmac.new(
        LICENSE_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
    # Modern UTC Timestamp (Naive for SQLAlchemy)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Validate License
    lic = (
        db.query(models.License)
        .filter(models.License.license_key == req.license_key, models.License.active == True)
        .first()
    )

    if not lic:
        raise HTTPException(status_code=404, detail="License invalid or revoked")

    # 2. Check Expiry
    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410, detail="License expired")

    # 3. Strict Device Binding
    existing_device = db.query(models.Device).filter_by(device_id=req.device_id).first()

    if existing_device:
        # Check if device is trying to use a different license
        if existing_device.license_id != lic.id:
            logger.warning(f"Device {req.device_id} attempted to switch licenses.")
            raise HTTPException(status_code=403, detail="Device bound to another license")
        
        # Update heartbeat
        existing_device.last_seen = now
        db.commit()
    else:
        # New binding: Check device limit
        count = db.query(models.Device).filter_by(license_id=lic.id).count()
        if count >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Maximum device limit reached")

        # Create binding
        db.add(models.Device(license_id=lic.id, device_id=req.device_id, last_seen=now))
        db.commit()

    # 4. Generate signed response
    expires = int(time.time()) + (OFFLINE_TTL_HOURS * 3600)
    token = {
        "license": req.license_key,
        "device": req.device_id,
        "exp": expires,
    }

    return {
        "status": "success",
        "token": token,
        "signature": sign_payload(token),
    }

# ----------------------------
# 5. Entry Point
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    # Use Render's $PORT or default 10000
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)