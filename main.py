import os
import hmac
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import engine, get_db
import models

app = FastAPI(title="License Server")

# -------------------------------------------------
# Schemas
# -------------------------------------------------
class VerifyRequest(BaseModel):
    license_key: str
    device_id: str

# -------------------------------------------------
# Helper: Verify Token
# -------------------------------------------------
def verify_token(device_id: str, timestamp: str, token: str, db: Session):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device or not device.shared_secret:
        return False

    # HMAC of the timestamp using the stored shared_secret
    expected = hmac.new(
        device.shared_secret.encode(),
        timestamp.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, token)

# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.post("/api/v1/register")
def register_device(request: VerifyRequest, db: Session = Depends(get_db)):
    # 1. Find the license
    lic = db.query(models.License).filter(models.License.license_key == request.license_key, models.License.active == True).first()
    if not lic:
        raise HTTPException(status_code=403, detail="Invalid license")

    # 2. Find or create the device
    device = db.query(models.Device).filter(models.Device.device_id == request.device_id).first()

    if not device:
        # Create new device with a fresh shared_secret
        new_secret = secrets.token_hex(16)
        device = models.Device(
            license_id=lic.id,
            device_id=request.device_id,
            shared_secret=new_secret
        )
        db.add(device)
        db.commit()
        db.refresh(device)

    # Return the secret so the extension can store it
    return {"status": "success", "shared_secret": device.shared_secret}

@app.post("/api/v1/rules")
def get_secure_rules(
    request: Request,
    body: dict,
    x_auth_token: str = Header(...),
    db: Session = Depends(get_db)
):
    device_id = body.get("device_id")
    timestamp = body.get("timestamp")

    if not device_id or not timestamp or not x_auth_token:
        raise HTTPException(status_code=400, detail="Missing auth parameters")

    if not verify_token(device_id, str(timestamp), x_auth_token, db):
        raise HTTPException(status_code=403, detail="Invalid auth token")

    # Success: update last_seen
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    device.last_seen = datetime.now(timezone.utc)
    db.commit()

    return {
        "isActive": True,
        "rules": [
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'message') and contains(.,'no USDT transaction')]",
            "//div[contains(@class,'commonModal-wrap')]//div[contains(@class,'buttonBox')]//div[contains(.,'Try Again Later')]"
        ]
    }

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)
