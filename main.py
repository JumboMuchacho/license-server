import os
import time
from datetime import datetime, timezone
import logging
import hmac
import hashlib
import json
from typing import Optional, List

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
# Setup & Config
# ----------------------------
load_dotenv()

LICENSE_SECRET = os.getenv("LICENSE_SECRET")
OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", 24))

# Production Logging: Set to WARNING to keep logs clean
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="License Server")

# ----------------------------
# 1. Health Checks (TOP PRIORITY)
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    return {"message": "License Server API is active"}

# ----------------------------
# 2. Routers & Static Files
# ----------------------------
app.include_router(admin_router)

# Mount the Admin UI
app.mount(
    "/admin-ui",
    StaticFiles(directory="static/admin", html=True),
    name="admin-ui",
)

# ----------------------------
# Database Initialization
# ----------------------------
@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
    # logger.warning used here so it shows up even in WARNING mode
    logger.warning("Database initialized and verified.")

# ----------------------------
# Schemas
# ----------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    client_version: Optional[str] = None

# ----------------------------
# Helper: Signing
# ----------------------------
def sign_payload(payload: dict) -> str:
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

# ----------------------------
# 3. Verify Route (with Auto-Transfer)
# ----------------------------
@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Look for the target license
    lic = (
        db.query(models.License)
        .filter(models.License.license_key == req.license_key, models.License.active == True)
        .first()
    )

    if not lic:
        raise HTTPException(status_code=404, detail="License invalid or revoked")

    # 2. Check if target license is expired
    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410, detail="License expired")

    # 3. Handle Device Binding & Migration Logic
    existing_device = db.query(models.Device).filter_by(device_id=req.device_id).first()

    if existing_device:
        # CASE A: Device is already on THIS license
        if existing_device.license_id == lic.id:
            existing_device.last_seen = now
            db.commit()
        else:
            # CASE B: Device is on a DIFFERENT license. Check if we can migrate.
            old_lic = db.query(models.License).filter_by(id=existing_device.license_id).first()
            
            # If old license is gone, revoked, or expired, allow the "jump"
            is_old_dead = not old_lic or not old_lic.active or (old_lic.expires_at and old_lic.expires_at < now)
            
            if is_old_dead:
                # Check capacity on NEW license before moving
                count = db.query(models.Device).filter_by(license_id=lic.id).count()
                if count >= lic.max_devices:
                    raise HTTPException(status_code=429, detail="Target license is full")

                existing_device.license_id = lic.id
                existing_device.last_seen = now
                db.commit()
                logger.warning(f"Device {req.device_id} migrated to license {lic.license_key}")
            else:
                # Old license is still valid! Prevent theft.
                raise HTTPException(status_code=403, detail="Device is still bound to another active license")
    else:
        # CASE C: Completely new device binding
        count = db.query(models.Device).filter_by(license_id=lic.id).count()
        if count >= lic.max_devices:
            raise HTTPException(status_code=429, detail="Maximum device limit reached")

        new_device = models.Device(
            license_id=lic.id,
            device_id=req.device_id,
            last_seen=now
        )
        db.add(new_device)
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

if __name__ == "__main__":
    import uvicorn
    # Default to 10000 for Render compatibility
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)