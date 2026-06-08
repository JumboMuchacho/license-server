import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import engine, get_db
import models
from admin_routes import router as admin_router
from update_routes import router as updates_router
from security import sign_payload

load_dotenv()

app = FastAPI(title="License Server")

app.include_router(admin_router)
app.include_router(updates_router)


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


@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
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
    # Token Lifetime Logic (UPDATED)
    # -------------------------------------------------

    if lic.expires_at:
        exp_time = int(lic.expires_at.timestamp())
    else:
        # Lifetime license fallback → 5 mins
        exp_time = int(time.time()) + 300

    token = {
        "license": req.license_key,
        "device": req.device_id,
        "exp": exp_time
    }

    return {
        "token": token,
        "signature": sign_payload(token),
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None
    }


@app.post("/api/v1/rules")
def get_monitoring_rules(req: RulesRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()

    # 1. Look up the license and ensure it is flagged active
    lic = db.query(models.License).filter(
        models.License.license_key == req.license_key,
        models.License.active == True
    ).first()

    # If license does not exist or has been administratively deactivated, return inactive state
    if not lic:
        return {"isActive": False, "rules": []}

    # 2. Check expiration date
    if lic.expires_at and lic.expires_at < now:
        return {"isActive": False, "rules": []}

    # 3. If valid, serve the monitoring layout hooks safely from the cloud
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
