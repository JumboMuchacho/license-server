import os
import time
import hmac
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional

from security import sign_payload
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import engine, get_db
import models
from admin_routes import router as admin_router
from updates_routes import router as updates_router

load_dotenv()

LICENSE_SECRET = os.getenv("LICENSE_SECRET")
OFFLINE_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS"))

app = FastAPI(title="License Server")

app.include_router(admin_router)
app.include_router(updates_router)

@app.get("/")
def root():
    return RedirectResponse("/admin-ui")

@app.get("/admin-ui")
def admin_ui():
    return FileResponse("static/admin/index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)

class VerifyRequest(BaseModel):
    license_key: str
    device_id: str
    version: Optional[str] = None

@app.post("/verify")
def verify(req: VerifyRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    lic = db.query(models.License).filter(
        models.License.license_key == req.license_key,
        models.License.active == True
    ).first()

    if not lic:
        raise HTTPException(status_code=404)

    if lic.expires_at and lic.expires_at < now:
        raise HTTPException(status_code=410)

    device = db.query(models.Device).filter_by(
        license_id=lic.id,
        device_id=req.device_id
    ).first()

    if not device:
        if lic.used_devices >= lic.max_devices:
            raise HTTPException(status_code=403)
        device = models.Device(
            license_id=lic.id,
            device_id=req.device_id,
            last_seen=now
        )
        db.add(device)
    else:
        device.last_seen = now

    db.commit()

    token = {
        "license": req.license_key,
        "device": req.device_id,
        "exp": int(time.time()) + OFFLINE_TTL_HOURS * 3600
    }

    return {
        "token": token,
        "signature": sign_payload(token)
    }
